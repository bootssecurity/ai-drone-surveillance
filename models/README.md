# AI Models Directory

This directory is for storing TensorFlow Lite models compatible with Google Coral Edge TPU.

## Required Models

The system requires the following models:

1. **Fire Detection Model**
   - File: `fire_model.tflite`
   - Labels: `fire_labels.txt`

2. **Person Detection Model**
   - File: `person_model.tflite`
   - Labels: `person_labels.txt`

3. **Suspicious Activity Model**
   - File: `suspicious_model.tflite`
   - Labels: `suspicious_labels.txt`

4. **Threat Detection Model**
   - File: `threat_model.tflite`
   - Labels: `threat_labels.txt`

## Model Formats

All models should be:
- TensorFlow Lite format (.tflite)
- Optimized for Edge TPU if using Google Coral
- Include label files in text format

## Obtaining Models

You can obtain these models from:

1. **Pre-trained models**: Google Coral provides pre-trained models for common tasks like person detection
   - Visit: https://coral.ai/models/

2. **Convert your own models**: Use the TensorFlow Lite converter and Edge TPU compiler
   - See: https://coral.ai/docs/edgetpu/compiler/

## Model Configuration

Models are configured in the `config/default_config.json` file under the `detection` section.
You can update the paths and thresholds as needed.