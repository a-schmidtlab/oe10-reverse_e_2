# RS232 Serial Communication Toolkit for Pan-Tilt Unit

## Functional Description

This toolkit contains software utilities for serial communication diagnostics with a pan-tilt unit via RS232 interface. The tools perform protocol analysis, signal verification, and communication testing based on captured data sequences.

## Directory Structure

```
├── data/             # Measurement data
│   └── raw/          # Raw capture files
├── docs/             # Technical documentation
│   ├── OE10_Software_Protocol.pdf  # Official protocol documentation
│   ├── protocol_analysis.md        # Communication protocol specification
│   └── test_protocol.md           # Test methodology and results
├── raw_data/         # Original data files
├── results/          # Test result data
│   └── logs/         # Application log files
├── src/              # Source code
│   ├── hex_terminal.py         # Command transmission interface
│   ├── pantilt_comm.py         # Basic communication module
│   ├── pantilt_protocol.py     # Protocol implementation
│   ├── pantilt_simulator.py    # Sequence simulator
│   └── rs232_verify.py         # Hardware verification tool
├── tests/            # Test suite directory
└── README.md         # This file
```

## Software Modules

### 1. Basic Communication Module (`src/pantilt_comm.py`)

Function: Initializes serial connection and transmits basic command sequences.

Usage:
```bash
python3 src/pantilt_comm.py --port /dev/ttyUSB0 --debug
```

Parameters:
- `--port`: Serial interface device
- `--baudrate`: Communication rate (default: 9600)
- `--test-all`: Execute parameter matrix test
- `--byte-by-byte`: Enable inter-byte delay mode
- `--debug`: Enable diagnostic output

### 2. Sequence Simulator (`src/pantilt_simulator.py`)

Function: Simulates protocol sequences from captured data.

Usage:
```bash
python3 src/pantilt_simulator.py --port /dev/ttyUSB0 --debug
```

Parameters:
- `--port`: Serial interface device
- `--baudrate`: Communication rate (default: 9600)
- `--debug`: Enable diagnostic output

### 3. Hardware Verification Tool (`src/rs232_verify.py`)

Function: Performs basic RS232 signal verification.

Usage:
```bash
python3 src/rs232_verify.py --port /dev/ttyUSB0
```

Parameters:
- `--port`: Serial interface device
- `--baudrate`: Communication rate (default: 9600)

### 4. Command Transmission Interface (`src/hex_terminal.py`)

Function: Provides interactive hex command transmission.

Usage:
```bash
python3 src/hex_terminal.py --port /dev/ttyUSB0
```

Control Commands:
- `byte XX`: Transmit single byte
- `init`: Transmit initialization sequence
- `hb`: Transmit heartbeat sequence
- `seq`: Execute complete sequence
- `q`: Terminate program

### 5. Protocol Implementation (`src/pantilt_protocol.py`)

Function: Implements comprehensive protocol variations with timing control.

Usage:
```bash
python3 src/pantilt_protocol.py --port /dev/ttyUSB0 --debug
```

Parameters:
- `--port`: Serial interface device
- `--baudrate`: Communication rate (default: 9600)
- `--debug`: Enable diagnostic output

## Installation Requirements

### System Requirements

- Python 3.6 or higher
- Serial port access permissions
- PySerial package

### Setup Procedure

1. Repository installation:
```bash
git clone https://github.com/username/pantilt-rs232-toolkit.git
cd pantilt-rs232-toolkit
```

2. Dependency installation:
```bash
pip install pyserial
```

3. Execute permission assignment:
```bash
chmod +x src/*.py
```

## Protocol Specification

The protocol specification is documented in the [Protocol Analysis](docs/protocol_analysis.md) file. Key properties include:

- Frame structure: Start marker (0x3C), payload, end marker (0x7C)
- Command sequence: Initialization, heartbeat maintenance
- Special character (0x5C) handling with timing considerations
- Positional encoding of movement parameters

## Test Results

The communication test procedures and results are documented in the [Test Protocol](docs/test_protocol.md) file.

**Test Summary:**

Multiple communication methods were tested but did not achieve successful data exchange with the device. The evidence suggests hardware interface issues rather than software implementation problems.

**Potential Failure Causes:**

1. Signal level incompatibility (TTL vs. RS232)
2. Signal path interruption
3. Power supply insufficiency
4. Hardware component failure

## Troubleshooting

Detailed troubleshooting procedures are available in the [Test Manual](docs/test_manual.md).

Recommended diagnostic steps:
- Signal level measurement with oscilloscope
- Transmission path verification
- Loopback testing of interface adapter
- Alternative hardware implementation testing

## License

MIT License

## Documentation Author

Axel Schmidt 