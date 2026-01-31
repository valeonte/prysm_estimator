"""
Ethereum Node Log Analyzer
Uses Claude API to analyze Erigon and Prysm logs for issues
"""

import anthropic
import os
import sys
from pathlib import Path
from datetime import datetime

# Configuration
API_KEY = os.environ.get("ANTHROPIC_API_KEY")  # Set this in your environment

# System prompt with your setup details
SYSTEM_PROMPT = """You are an Ethereum node troubleshooting expert analyzing logs from a dual-node setup."""

def read_log_tail(filepath, lines=100):
    """Read the last N lines from a log file"""
    try:
        with open(filepath, 'r') as f:
            # Read all lines and get the last N
            all_lines = f.readlines()
            return ''.join(all_lines[-lines:])
    except FileNotFoundError:
        return f"ERROR: Log file not found at {filepath}"
    except Exception as e:
        return f"ERROR reading {filepath}: {str(e)}"


def analyze_logs(erigon_logs, prysm_logs, custom_question=None):
    """Send logs to Claude API for analysis"""

    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-api-key-here'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=API_KEY)

    # Construct the user message
    user_message = f"""Please analyze these Ethereum node logs.

### Erigon Logs (Execution Layer)
```
{erigon_logs}
```

### Prysm Logs (Consensus Layer)
```
{prysm_logs}
```
"""

    if custom_question:
        user_message += f"\n### Specific Question\n{custom_question}\n"

    # Call Claude API
    print("Analyzing logs with Claude Sonnet 4.5...\n")

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        return message.content[0].text  # type: ignore

    except anthropic.APIError as e:
        return f"API Error: {str(e)}"


def main():
    """Main function to run the log analyzer"""

    print("=" * 80)
    print("Ethereum Node Log Analyzer")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Determine mode based on arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print(__doc__)
            print("\nUsage:")
            print("  ./analyze_logs.py                    # Analyze last 100 lines from both logs")
            print("  ./analyze_logs.py 200                # Analyze last 200 lines")
            print("  ./analyze_logs.py --files e.log p.log # Analyze specific files")
            print("  ./analyze_logs.py --stdin            # Read logs from stdin")
            print("\nEnvironment Variables:")
            print("  ANTHROPIC_API_KEY - Your Anthropic API key (required)")
            print("  ERIGON_LOG        - Override default Erigon log path")
            print("  PRYSM_LOG         - Override default Prysm log path")
            return

        if sys.argv[1] == "--stdin":
            print("Paste Erigon logs, then press Ctrl+D:")
            erigon_logs = sys.stdin.read()
            print("\nNow paste Prysm logs, then press Ctrl+D:")
            prysm_logs = sys.stdin.read()

        elif sys.argv[1] == "--files" and len(sys.argv) >= 4:
            erigon_file = sys.argv[2]
            prysm_file = sys.argv[3]
            print(f"Reading Erigon logs from: {erigon_file}")
            print(f"Reading Prysm logs from: {prysm_file}")
            erigon_logs = read_log_tail(erigon_file, lines=999999)  # Read entire file
            prysm_logs = read_log_tail(prysm_file, lines=999999)

        elif sys.argv[1].isdigit():
            lines = int(sys.argv[1])
            print(f"Reading last {lines} lines from default log locations...")
            erigon_logs = read_log_tail(
                os.environ.get("ERIGON_LOG"),
                lines=lines
            )
            prysm_logs = read_log_tail(
                os.environ.get("PRYSM_LOG"),
                lines=lines
            )
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
            return
    else:
        # Default: read last 100 lines
        print("Reading last 100 lines from default log locations...")
        erigon_logs = read_log_tail(
            os.environ.get("ERIGON_LOG"),
            lines=100
        )
        prysm_logs = read_log_tail(
            os.environ.get("PRYSM_LOG"),
            lines=100
        )

    print()

    # Analyze
    analysis = analyze_logs(erigon_logs, prysm_logs)

    # Output
    print(analysis)
    print()
    print("=" * 80)

    # Optionally save to file
    output_file = f"log_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(output_file, 'w') as f:
        f.write(f"Analysis generated at: {datetime.now()}\n")
        f.write("=" * 80 + "\n\n")
        f.write(analysis)

    print(f"Analysis saved to: {output_file}")


if __name__ == "__main__":
    main()
