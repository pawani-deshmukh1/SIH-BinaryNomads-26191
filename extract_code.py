import os

def extract_code(root_dir, output_file):
    allowed_extensions = {'.py', '.html', '.js', '.css', '.sql'}
    ignored_dirs = {'venv', '.venv', 'env', '.env', 'node_modules', '__pycache__', '.git', '.idea', '.vscode', '.gemini'}

    with open(output_file, 'w', encoding='utf-8') as out:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Modify dirnames in-place to skip ignored directories
            dirnames[:] = [d for d in dirnames if d not in ignored_dirs]
            
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in allowed_extensions:
                    filepath = os.path.join(dirpath, filename)
                    
                    # Skip the script itself and the output file if it matches
                    if os.path.abspath(filepath) == os.path.abspath(__file__):
                        continue
                        
                    out.write(f"\n{'='*80}\n")
                    # Make path relative to root_dir for cleaner output
                    rel_path = os.path.relpath(filepath, root_dir)
                    out.write(f"File: {rel_path}\n")
                    out.write(f"{'='*80}\n\n")
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as infile:
                            out.write(infile.read())
                    except Exception as e:
                        out.write(f"# Error reading file: {e}\n")

if __name__ == "__main__":
    # Get the directory where this script is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_filename = os.path.join(current_dir, 'all_code.txt')
    
    extract_code(current_dir, output_filename)
    print(f"Code extracted successfully to: {output_filename}")
