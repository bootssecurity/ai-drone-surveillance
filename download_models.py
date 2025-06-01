#!/usr/bin/env python3

import os
import argparse
import requests
import logging
import sys
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ModelDownloader")

# Default model URLs
# These are examples - replace with actual model URLs
DEFAULT_MODELS = {
    "person_model": {
        "url": "https://github.com/google-coral/test_data/raw/master/ssd_mobilenet_v2_coco_quant_postprocess_edgetpu.tflite",
        "path": "models/person_model.tflite"
    },
    "person_labels": {
        "url": "https://github.com/google-coral/test_data/raw/master/coco_labels.txt",
        "path": "models/person_labels.txt"
    },
    # Add placeholders for other models
    # In a real system, you would provide actual URLs
    "fire_model": {
        "url": "https://example.com/models/fire_model.tflite",
        "path": "models/fire_model.tflite"
    },
    "fire_labels": {
        "url": "https://example.com/models/fire_labels.txt",
        "path": "models/fire_labels.txt"
    },
    "suspicious_model": {
        "url": "https://example.com/models/suspicious_model.tflite",
        "path": "models/suspicious_model.tflite"
    },
    "suspicious_labels": {
        "url": "https://example.com/models/suspicious_labels.txt",
        "path": "models/suspicious_labels.txt"
    },
    "threat_model": {
        "url": "https://example.com/models/threat_model.tflite",
        "path": "models/threat_model.tflite"
    },
    "threat_labels": {
        "url": "https://example.com/models/threat_labels.txt",
        "path": "models/threat_labels.txt"
    }
}

def download_file(url, output_path, force=False):
    """
    Download a file from a URL to a local path.
    
    Args:
        url (str): URL to download from
        output_path (str): Local path to save the file
        force (bool): Whether to overwrite existing files
    
    Returns:
        bool: True if downloaded successfully
    """
    # Check if file already exists
    if os.path.exists(output_path) and not force:
        logger.info(f"File already exists: {output_path}")
        return True
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        logger.info(f"Downloading {url} to {output_path}")
        
        # Stream download with progress bar
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1 KB
        
        with open(output_path, 'wb') as f, tqdm(
            desc=os.path.basename(output_path),
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024
        ) as pbar:
            for data in response.iter_content(block_size):
                f.write(data)
                pbar.update(len(data))
        
        logger.info(f"Downloaded successfully: {output_path}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download {url}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error downloading {url}: {str(e)}")
        return False

def download_models(models, force=False):
    """
    Download all specified models.
    
    Args:
        models (dict): Dictionary of models to download
        force (bool): Whether to overwrite existing files
    
    Returns:
        int: Number of models downloaded successfully
    """
    success_count = 0
    
    for name, model_info in models.items():
        try:
            if download_file(model_info['url'], model_info['path'], force):
                success_count += 1
            else:
                logger.warning(f"Failed to download {name}")
        except Exception as e:
            logger.error(f"Error processing {name}: {str(e)}")
    
    return success_count

def main():
    """Main function to parse arguments and download models."""
    parser = argparse.ArgumentParser(description='Download AI models for drone surveillance system')
    parser.add_argument('--force', action='store_true', help='Force download even if files exist')
    parser.add_argument('--model', help='Download only a specific model')
    args = parser.parse_args()
    
    if args.model:
        if args.model in DEFAULT_MODELS:
            # Download specific model
            if download_file(
                DEFAULT_MODELS[args.model]['url'],
                DEFAULT_MODELS[args.model]['path'],
                args.force
            ):
                logger.info(f"Successfully downloaded {args.model}")
            else:
                logger.error(f"Failed to download {args.model}")
        else:
            logger.error(f"Unknown model: {args.model}")
            logger.info(f"Available models: {', '.join(DEFAULT_MODELS.keys())}")
    else:
        # Download all models
        count = download_models(DEFAULT_MODELS, args.force)
        logger.info(f"Downloaded {count}/{len(DEFAULT_MODELS)} models")

if __name__ == "__main__":
    main() 