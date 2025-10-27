"""
Backend Interface for ELI Compiler
All compiler backends must inherit from CompilerBackend
"""

from abc import ABC, abstractmethod

class CompilerBackend(ABC):
    """
    Abstract base class for all ELI compiler backends

    Each backend must implement:
    - compile(opcodes, output_file): Generate native code
    - get_output_filename(base_name): Return appropriate filename
    """

    def __init__(self):
        self.description = "Generic compiler backend"
        self.architecture = "unknown"

    @abstractmethod
    def compile(self, opcodes, output_file):
        """
        Compile ELI opcodes to native binary

        Args:
            opcodes (str): Preprocessed ELI opcodes (space-separated)
            output_file (str): Path for output binary

        Returns:
            bool: True if compilation succeeded, False otherwise
        """
        pass

    @abstractmethod
    def get_output_filename(self, base_name):
        """
        Get appropriate output filename for this architecture

        Args:
            base_name (str): Base name without extension

        Returns:
            str: Full output filename with appropriate extension
        """
        pass

    def parse_opcodes(self, opcodes):
        """
        Parse opcode string into tokens

        Returns:
            list: List of (type, value) tuples
                  type: 'OP' for operation, 'LIT' for literal
        """
        tokens = []
        for token in opcodes.split():
            token = token.strip()
            if not token:
                continue

            # Check if it's a number (literal)
            if self._is_number(token):
                tokens.append(('LIT', int(token)))
            else:
                # It's an operation
                tokens.append(('OP', token))

        return tokens

    def _is_number(self, s):
        """Check if string is a number"""
        try:
            int(s)
            return True
        except ValueError:
            # Check for negative numbers
            if s.startswith('-'):
                try:
                    int(s[1:])
                    return True
                except ValueError:
                    pass
            return False

    def error(self, message):
        """Print error message"""
        print(f"Backend Error [{self.architecture}]: {message}")

    def info(self, message):
        """Print info message"""
        print(f"[{self.architecture}] {message}")
