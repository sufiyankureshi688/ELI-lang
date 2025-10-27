#!/usr/bin/env python3
"""
alpha_c2 - ELI Native Compiler (Refactored)
Compiles ELI opcodes directly to native machine code
"""

import sys
import os

class AlphaC2:
    """
    ELI Compiler - Converts ELI opcodes to native binaries
    Architecture: Modular backend system
    """

    def __init__(self, debug=False):
        self.debug = debug
        self.backends = {}
        self.load_backends()

    def load_backends(self):
        """Load available compiler backends"""
        backend_dir = 'backend'
        if not os.path.exists(backend_dir):
            print(f"Warning: Backend directory '{backend_dir}' not found")
            return

        # Import backend interface
        try:
            from backend.backend_interface import CompilerBackend
            self.backend_interface = CompilerBackend
        except ImportError as e:
            print(f"Warning: Could not load backend interface: {e}")
            return

        # Load individual backends
        backend_files = [f for f in os.listdir(backend_dir) 
                        if f.endswith('.py') and f != 'backend_interface.py']

        for backend_file in backend_files:
            backend_name = backend_file.replace('.py', '')
            try:
                backend_module = self._import_backend(f'{backend_dir}/{backend_file}')
                if hasattr(backend_module, 'Backend'):
                    self.backends[backend_name] = backend_module.Backend
                    if self.debug:
                        print(f"✓ Loaded backend: {backend_name}")
            except Exception as e:
                print(f"✗ Failed to load backend '{backend_name}': {e}")

    def _import_backend(self, backend_path):
        """Dynamically import a backend module"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("backend", backend_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def list_architectures(self):
        """List available target architectures"""
        print("\n=== Available Architectures ===")
        if not self.backends:
            print("No backends available")
            return

        for name, backend_class in self.backends.items():
            try:
                backend = backend_class()
                print(f" • {name}")
                if hasattr(backend, 'description'):
                    print(f"   {backend.description}")
            except Exception as e:
                print(f" • {name} (Error: {e})")
        print()

    def compile(self, opcodes, output_file, architecture=None):
        """
        Compile ELI opcodes to native binary

        Args:
            opcodes: String of space-separated ELI opcodes
            output_file: Output binary path
            architecture: Target architecture (if None, prompts user)
        """

        # Validate opcodes
        if not opcodes or not isinstance(opcodes, str):
            print("Error: Invalid opcodes - must be a non-empty string")
            return False

        if self.debug:
            print(f"Input opcodes: {opcodes[:100]}...")

        # Select architecture
        if architecture is None:
            architecture = self._prompt_architecture()
            if architecture is None:
                return False

        # Get backend
        if architecture not in self.backends:
            print(f"Error: Unknown architecture '{architecture}'")
            print(f"Available: {', '.join(self.backends.keys())}")
            return False

        # Initialize backend
        try:
            backend = self.backends[architecture]()
            print(f"=== Compiling for {architecture} ===")
        except Exception as e:
            print(f"Error initializing backend: {e}")
            return False

        # Determine output file
        if hasattr(backend, 'get_output_filename'):
            base_name = os.path.splitext(output_file)[0]
            output_file = backend.get_output_filename(base_name)

        # Compile
        try:
            success = backend.compile(opcodes, output_file)
            if success:
                print(f"\n✓ Compilation successful!")
                print(f"  Output: {output_file}")

                # Make executable (Unix-like systems)
                if hasattr(os, 'chmod'):
                    os.chmod(output_file, 0o755)
                    print(f"  Permissions: executable")

                print(f"\n  Run with: ./{output_file}")
                return True
            else:
                print(f"\n✗ Compilation failed")
                return False

        except Exception as e:
            print(f"Compilation error: {e}")
            import traceback
            if self.debug:
                traceback.print_exc()
            return False

    def compile_from_file(self, opcode_file, output_file=None, architecture=None):
        """
        Compile ELI opcodes from a file

        Args:
            opcode_file: Path to file containing ELI opcodes
            output_file: Output binary path (default: opcode_file without extension)
            architecture: Target architecture (if None, prompts user)
        """

        # Read opcodes from file
        try:
            with open(opcode_file, 'r') as f:
                opcodes = f.read().strip()
        except FileNotFoundError:
            print(f"Error: Opcode file '{opcode_file}' not found")
            return False
        except Exception as e:
            print(f"Error reading file: {e}")
            return False

        # Determine output file
        if output_file is None:
            output_file = os.path.splitext(opcode_file)[0]

        print(f"Reading opcodes from: {opcode_file}")

        # Compile
        return self.compile(opcodes, output_file, architecture)

    def _prompt_architecture(self):
        """Prompt user to select target architecture"""
        if not self.backends:
            print("Error: No backends available")
            return None

        print("\nSelect target architecture:")
        arch_list = list(self.backends.keys())
        for i, arch in enumerate(arch_list, 1):
            print(f"  {i}. {arch}")

        try:
            choice = input("\nEnter number (or name): ").strip()

            # Try as number first
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(arch_list):
                    return arch_list[idx]

            # Try as name
            if choice in self.backends:
                return choice

            print(f"Invalid choice: {choice}")
            return None

        except (KeyboardInterrupt, EOFError):
            print("\nCancelled")
            return None


def main():
    """Command-line interface"""
    import argparse

    examples = """
examples:
  Compile opcode string:
    python3 alpha_c2.py "10 20 A P H" -o myprogram -a arm64

  Compile from file:
    python3 alpha_c2.py opcodes.eli -f -o myprogram -a arm64

  List architectures:
    python3 alpha_c2.py -l
"""

    parser = argparse.ArgumentParser(
        description='ELI Native Compiler - Compile ELI opcodes to native binaries',
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('input', nargs='?', 
                       help='Opcode string or file path (use -f for files)')
    parser.add_argument('-o', '--output', help='Output binary file')
    parser.add_argument('-a', '--arch', help='Target architecture')
    parser.add_argument('-f', '--file', action='store_true',
                       help='Treat input as file path containing opcodes')
    parser.add_argument('-l', '--list', action='store_true',
                       help='List available architectures')
    parser.add_argument('-d', '--debug', action='store_true',
                       help='Enable debug output')

    args = parser.parse_args()

    compiler = AlphaC2(debug=args.debug)

    # List architectures
    if args.list:
        compiler.list_architectures()
        return

    # Require input
    if not args.input:
        parser.print_help()
        print("\nUse -l to list available architectures")
        sys.exit(1)

    # Auto-detect file mode if input looks like a file path
    is_file = args.file
    if not is_file and os.path.exists(args.input):
        print(f"Note: Detected '{args.input}' as file. Use -f flag to suppress this message.")
        is_file = True

    # Determine output file
    output = args.output
    if output is None:
        if is_file:
            output = os.path.splitext(args.input)[0]
        else:
            output = 'output'

    # Compile from file or string
    if is_file:
        success = compiler.compile_from_file(args.input, output, args.arch)
    else:
        success = compiler.compile(args.input, output, args.arch)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
