# NeHe Atari 2600 Smart Disassembler

An advanced, intelligent disassembler for Atari 2600 ROMs. Uses code flow analysis, CPU simulation, and pattern recognition to produce clean, reassemblable 6502 assembly output.

**Created by Jeff Molofee (NeHe) — 2026**

## Features

### 🎯 Intelligent Code Analysis
- **Code Flow Analysis** — Recursive descent from the RESET vector to trace all reachable code
- **CPU Simulation** — Exhaustive static execution tracing for near-100% code coverage
- **Code/Data Separation** — Automatically distinguishes instructions from binary data
- **Variable Tracking** — Identifies and names zero-page RAM variables
- **Pattern Recognition** — Detects VBLANK routines, sprite kernels, timer sequences, and more
- **Cross-References** — Tracks subroutine call relationships

### 🏦 Bank Switching Support
- **F8 (8K)** — 2 × 4K banks
- **F6 (16K)** — 4 × 4K banks
- **F4 (32K)** — 8 × 4K banks
- **FA (12K)** — 3 × 4K banks (CBS)
- **FE (8K)** — 2 × 4K banks (Activision)
- **3F** — Variable size (Tigervision)
- Automatic hotspot detection and bank mapping

### 📚 Complete 6502/6507 Opcode Support
- All legal 6502 opcodes
- Full illegal/undocumented opcode support
- Processor flag annotations (N, V, Z, C)
- Operation descriptions (e.g., `A = M`, `A = A + M + C`)
- Accurate CPU cycle counts per instruction

### 🎨 High-Quality Output
- **Reassemblable** — Output is designed to be fed directly into the NeHe Atari 2600 Assembler
- **Symbol Resolution** — Uses standard Atari 2600 hardware register names (WSYNC, GRP0, etc.)
- **Smart Comments** — Context-aware comments for TIA/RIOT register accesses
- **Data Visualization** — ASCII art representation of sprite graphics data
- **TIA Data Labeling** — Automatically labels ROM data blocks by hardware usage (graphics, audio, etc.)

## Quick Start

### Standalone Executable

Download the prebuilt Windows executable from the [Releases](../../releases) page (no Python required):

```
NeHe-Atari2600-Disassembler.exe rom\game.a26
```

### Using Python

```bash
python disassembler.py rom/game.a26
```

### With Options

```bash
# Add comments and cycle counts
python disassembler.py rom/game.a26 --comments --cycles

# Full-featured output
python disassembler.py rom/game.a26 --comments --cycles --show-flags --show-operations --xrefs

# Save to file
python disassembler.py rom/game.a26 -o output.asm
```

## Command-Line Options

| Flag | Description |
|------|-------------|
| `-o <file>` | Write output to file (default: stdout) |
| `--comments` | Enable context-aware instruction comments |
| `--cycles` | Show CPU cycle counts per instruction |
| `--show-flags` | Show processor flags affected (N, V, Z, C) |
| `--show-operations` | Show operation descriptions (e.g., `A = M`) |
| `--xrefs` | Show cross-references between subroutines |
| `--visualize-data` | Render graphics data as ASCII art |
| `--addresses` | Prefix each instruction with its memory address |
| `--hex` | Show raw hex bytes for each instruction |
| `--disable-labels` | Disable automatic label generation |

## Example Output

```asm
; ============================================================================
; SUBROUTINE - 15 bytes
; Called from: 2 locations
; ============================================================================

Subroutine_F00C:
  CMP    #$00             ; Compare accumulator
  BNE    Branch_F014      ; Branch if not equal (not zero)
  LDA    #$01             ; Load accumulator
  STA    <WSYNC           ; Wait for horizontal blank
  RTS                     ; Return from subroutine
```

With `--cycles --show-flags --show-operations`:

```asm
  CMP    #$00      ; [     2] | Flags: N Z C | A - M          | Compare accumulator
  BNE    Branch    ; [ 2+t+p] |              | Branch if Z = 0 | Branch if not equal
  LDA    #$01      ; [     2] | Flags: N Z   | A = M          | Load accumulator
  STA    <WSYNC    ; [     3] |              | M = A          | Wait for horizontal blank
  RTS              ; [     6] |              | Pull PC, PC+1  | Return from subroutine
```

## Project Structure

```
NeHe - Atari 2600 Disassembler/
├── disassembler.py          # Main entry point — code flow analysis and output generation
├── core_opcodes.py          # Complete 6502/6507 opcode table, flags, cycle counts
├── symbols_and_tracking.py  # Hardware register symbols, variable tracker, cross-referencer
├── analyzers.py             # Pattern recognition, code section analysis, data comments
├── banking.py               # Bank switching detection and address mapping
├── cpu_simulator.py         # Static CPU execution tracer for deep code coverage
├── README.md                # This file
└── rom/                     # Place your .a26 ROM files here (not included)
```

## How It Works

### Step 1 — Bank Switching Detection

The disassembler first determines the ROM size and detects the bank switching scheme by scanning for hotspot address accesses in the binary.

### Step 2 — Code Flow Analysis (Static Pass)

Starting from the RESET vector (`$FFFC–$FFFD`), the disassembler performs recursive descent:
- Follows `JSR`/`JMP` targets
- Traces both sides of branch instructions
- Stops at `RTS`/`RTI`/unconditional `JMP`

### Step 3 — CPU Simulation (Deep Pass)

After the static pass, a static CPU execution simulator seeds every ROM byte as a potential entry point and traces all reachable code paths. This produces near-100% code coverage and catches code unreachable from the RESET vector alone.

### Step 4 — Variable & Pattern Analysis

- Zero-page RAM accesses are tracked and named (e.g., `Var_80`, pointer pairs)
- Common Atari 2600 patterns are identified (VBLANK timing, sprite kernels, etc.)
- TIA register write chains are traced backward to label ROM data blocks

### Step 5 — Label Generation

Labels are created only for real jump/call/branch targets:
- `Subroutine_XXXX` — JSR targets that end with RTS/RTI
- `Jump_XXXX` — JMP targets
- `Branch_XXXX` — conditional branch targets
- `GraphicsData_XXXX`, `AudioData_XXXX`, etc. — ROM data blocks identified by TIA usage

### Step 6 — Assembly Output

The final pass writes the assembly file with:
- Correct `ORG` directives for each bank
- All code as instructions with optional comments
- All data regions as `.byte` sequences
- Symbol definitions for zero-page variables and hardware registers

## ROM Placement

Place your `.a26` ROM files in the `rom/` folder:

```
rom/
├── game.a26
└── another_game.a26
```

Then run:

```bash
python disassembler.py rom/game.a26 -o rom/game.asm
```

> **Note:** ROM files are not included. Only supply ROMs you legally own.

## Building the Executable

The GitHub Actions workflow in `.github/workflows/build.yml` automatically builds the Windows executable on every push and release using PyInstaller.

To build locally:

```bash
pip install pyinstaller
pyinstaller --onefile --name "NeHe-Atari2600-Disassembler" --console disassembler.py
```

The executable will be created in the `dist/` folder.

## Requirements

- Python 3.8 or higher
- No external dependencies

## References

- [6502.org Opcode Tutorial](http://www.6502.org/tutorials/6502opcodes.html)
- [Masswerk 6502 Instruction Set](https://www.masswerk.at/6502/6502_instruction_set.html)
- [Atari 2600 Advanced Programming Guide](https://www.atarihq.com/danb/files/2600_Advanced_Programming_Guide.txt)
- [Stella Programmer's Guide](https://alienbill.com/2600/101/docs/stella.html)

## License

Created by Jeff Molofee (NeHe) 2026  
Free to use and modify
