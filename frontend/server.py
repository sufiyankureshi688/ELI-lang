#!/usr/bin/env python3
"""
ELI Language Server
Run: python3 server.py
Then open: http://localhost:5000
"""

import sys
import os
import io
import subprocess
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import traceback

# Add src to path
SRC_DIR = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, SRC_DIR)

from alpha_i2 import ALPHA_2
from alpha_p3 import preprocess, FrontendError

KEYWORDS_DIR = os.path.join(SRC_DIR, 'library', 'keywords')
PORT = 8080


def run_raw(code: str) -> dict:
    """Interpret raw ELI (.eli) code, capture stdout."""
    output_lines = []
    errors = []

    # Patch print to capture output
    import builtins
    original_print = builtins.print

    def capture_print(*args, **kwargs):
        end = kwargs.get('end', '\n')
        sep = kwargs.get('sep', ' ')
        text = sep.join(str(a) for a in args) + end
        output_lines.append(text)

    builtins.print = capture_print

    try:
        vm = ALPHA_2()
        # Strip comments
        lines = []
        for line in code.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                lines.append(line)
        clean = '\n'.join(lines)
        final_stack = vm.execute(clean)
        if final_stack is not None:
            output_lines.append(f"Final stack: {final_stack}")
    except Exception as e:
        errors.append(f"Runtime error: {e}")
        errors.append(traceback.format_exc())
    finally:
        builtins.print = original_print

    return {
        "output": "".join(output_lines),
        "errors": "\n".join(errors),
        "compiled": None
    }


def run_sugar(code: str, compile_only: bool = False) -> dict:
    """Preprocess ELI Sugar (.eli2) and optionally run it."""
    output_lines = []
    errors = []
    compiled_code = None

    try:
        compiled_code = preprocess(code, keywords_dir=KEYWORDS_DIR)
    except FrontendError as e:
        errors.append(f"Compile error: {e}")
        return {"output": "", "errors": "\n".join(errors), "compiled": None}
    except Exception as e:
        errors.append(f"Unexpected compile error: {e}")
        errors.append(traceback.format_exc())
        return {"output": "", "errors": "\n".join(errors), "compiled": None}

    if compile_only:
        return {"output": "", "errors": "", "compiled": compiled_code}

    # Run compiled output
    import builtins
    original_print = builtins.print

    def capture_print(*args, **kwargs):
        end = kwargs.get('end', '\n')
        sep = kwargs.get('sep', ' ')
        text = sep.join(str(a) for a in args) + end
        output_lines.append(text)

    builtins.print = capture_print

    try:
        vm = ALPHA_2()
        final_stack = vm.execute(compiled_code)
        if final_stack is not None:
            output_lines.append(f"Final stack: {final_stack}")
    except Exception as e:
        errors.append(f"Runtime error: {e}")
        errors.append(traceback.format_exc())
    finally:
        builtins.print = original_print

    return {
        "output": "".join(output_lines),
        "errors": "\n".join(errors),
        "compiled": compiled_code
    }


class ELIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default access logs

    def send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            index_path = os.path.join(os.path.dirname(__file__), 'index.html')
            try:
                with open(index_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_cors()
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'index.html not found')
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "version": "ELI v10.0"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body)
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Bad JSON')
            return

        code = data.get('code', '')
        mode = data.get('mode', 'raw')          # 'raw' or 'sugar'
        action = data.get('action', 'run')       # 'run' or 'compile'

        if self.path == '/run':
            if mode == 'sugar':
                result = run_sugar(code, compile_only=(action == 'compile'))
            else:
                result = run_raw(code)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors()
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_response(404)
            self.end_headers()


def open_browser():
    import time
    time.sleep(0.8)
    webbrowser.open(f'http://localhost:{PORT}')


if __name__ == '__main__':
    print(f"""
  ███████╗██╗     ██╗
  ██╔════╝██║     ██║
  █████╗  ██║     ██║
  ██╔══╝  ██║     ██║
  ███████╗███████╗██║
  ╚══════╝╚══════╝╚═╝
  Emergent Language Interface v10.0
  Server running at http://localhost:{PORT}
""")

    threading.Thread(target=open_browser, daemon=True).start()

    server = HTTPServer(('localhost', PORT), ELIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
