import json
import os
import glob

def validate_prediction_format(pred):
    """Validate and fix prediction format"""
    required_fields = {
        'item_id': int,
        'class_index': int,
        'class_name': str,
        'confidence': float,
        'bounding_box': list,
        'mask_data': list
    }
    
    for field, field_type in required_fields.items():
        if field not in pred:
            return False
        if not isinstance(pred[field], field_type):
            return False
    return True

def fix_json_file(file_path):
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Try to parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"JSON decode error in {file_path} at line {e.lineno}, column {e.colno}")
            print(f"Error message: {e.msg}")
            # Get context around the error
            lines = content.split('\n')
            error_line = e.lineno - 1
            context_start = max(0, error_line - 5)
            context_end = min(len(lines), error_line + 5)
            print("\nContext around error:")
            for i in range(context_start, context_end):
                prefix = ">>> " if i == error_line else "    "
                print(f"{prefix}{i+1}: {lines[i]}")
            return False
            
        # Validate format
        if not isinstance(data, dict):
            print(f"Error: Root element should be an object in {file_path}")
            return False
            
        required_fields = {'batch_id', 'timestamp', 'image_path', 'model_version', 'predictions'}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            print(f"Error: Missing required fields {missing_fields} in {file_path}")
            return False
            
        # Validate predictions
        if not isinstance(data['predictions'], list):
            print(f"Error: 'predictions' should be an array in {file_path}")
            return False
            
        for i, pred in enumerate(data['predictions']):
            if not validate_prediction_format(pred):
                print(f"Error: Invalid prediction format at index {i} in {file_path}")
                return False
                
        # If everything is valid, rewrite the file with proper formatting
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Successfully validated and reformatted {file_path}")
        return True
        
    except Exception as e:
        print(f"Unexpected error in {file_path}: {str(e)}")
        return False

def main():
    prediction_dir = "validation_data/predictions"
    # Sort files by modification time to process most recent first
    json_files = sorted(
        glob.glob(os.path.join(prediction_dir, "*.json")),
        key=lambda x: os.path.getmtime(x),
        reverse=True
    )
    
    print(f"Found {len(json_files)} JSON files")
    fixed = 0
    errors = 0
    
    for file_path in json_files:
        print(f"\nProcessing {os.path.basename(file_path)}...")
        if fix_json_file(file_path):
            fixed += 1
        else:
            errors += 1
            
    print(f"\nFinal Summary:")
    print(f"Total files processed: {len(json_files)}")
    print(f"Files fixed: {fixed}")
    print(f"Files with errors: {errors}")

if __name__ == "__main__":
    main()
