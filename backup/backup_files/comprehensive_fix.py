#!/usr/bin/env python3
import os

def fix_tiered_cache():
    file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/tiered_cache.py'

    print(f"Reading file: {file_path}")
    # Read the file
    try:
        with open(file_path, 'r') as f:
            content = f.readlines()
        print(f"Successfully read file with {len(content)} lines")
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Find the _discover_partitions method
    start_line = -1
    end_line = -1

    for i, line in enumerate(content):
        if 'def _discover_partitions' in line:
            start_line = i
            print(f"Found _discover_partitions method at line {start_line}")
        if start_line != -1 and line.strip() == '' and i > start_line and end_line == -1:
            # Found the end of the method
            end_line = i
            print(f"Found end of method at line {end_line}")
            break

    # If we didn't find the end, assume it's the last line
    if end_line == -1:
        end_line = len(content)
        print(f"Could not find end of method, assuming it's the last line: {end_line}")

    # Create the fixed version of the method
    fixed_method = [
        '    def _discover_partitions(self) -> Dict[int, Dict[str, Any]]:\n',
        '        """Discover existing partition files."""\n',
        '        partitions = {}\n',
        '        for filename in os.listdir(self.directory):\n',
        '            if not filename.startswith(\'cid_cache_\') or not filename.endswith(\'.parquet\'):\n',
        '                continue\n',
        '                \n',
        '            try:\n',
        '                # Extract partition ID from filename\n',
        '                partition_id = int(filename.split(\'_\')[2].split(\'.\')[0])\n',
        '                partition_path = os.path.join(self.directory, filename)\n',
        '                \n',
        '                # Get metadata without loading full content\n',
        '                try:\n',
        '                    metadata = pq.read_metadata(partition_path)\n',
        '                    \n',
        '                    partitions[partition_id] = {\n',
        '                        \'path\': partition_path,\n',
        '                        \'size\': os.path.getsize(partition_path),\n',
        '                        \'rows\': metadata.num_rows,\n',
        '                        \'created\': os.path.getctime(partition_path),\n',
        '                        \'modified\': os.path.getmtime(partition_path)\n',
        '                    }\n',
        '                except Exception as e:\n',
        '                    logger.warning(f"Invalid partition file {filename}: {e}")\n',
        '            except Exception as e:\n',
        '                logger.warning(f"Could not process partition file {filename}: {e}")\n',
        '                \n',
        '        return partitions\n',
        '\n'
    ]

    # Replace the old method with the fixed version
    print(f"Replacing method from line {start_line} to {end_line} with fixed version")
    content[start_line:end_line] = fixed_method

    # Write the fixed content back
    try:
        with open(file_path, 'w') as f:
            f.writelines(content)
        print(f"Successfully wrote fixed content back to file")
    except Exception as e:
        print(f"Error writing to file: {e}")

    print(f"Fixed _discover_partitions method in tiered_cache.py")

if __name__ == "__main__":
    fix_tiered_cache()
