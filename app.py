from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import os
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from tensorflow.keras.models import load_model
import numpy as np
from PIL import Image
import io
import datetime
import shutil

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'dcm'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

try:
    model = load_model('model.keras')
    print("Model loaded successfully")
except Exception as e:
    print(f"Error loading model: {str(e)}")
    model = None

CLASS_LABELS = {
    0: "Normal",
    1: "Abnormal"
}

def clear_uploads_folder():
    """Clear the uploads folder completely"""
    if os.path.exists(app.config['UPLOAD_FOLDER']):
        shutil.rmtree(app.config['UPLOAD_FOLDER'])
    os.makedirs(app.config['UPLOAD_FOLDER'])

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def dicom_to_array(dicom_path):
    """Convert DICOM file to numpy array"""
    try:
        ds = pydicom.dcmread(dicom_path)
        img_array = ds.pixel_array
        img_array = img_array.astype('float32') / img_array.max()
        if len(img_array.shape) == 2:
            img_array = np.stack((img_array,)*3, axis=-1)
        return img_array, ds
    except Exception as e:
        print(f"Error reading DICOM: {str(e)}")
        raise

def prepare_image(img_array, target_size):
    """Preprocess numpy array for model prediction"""
    try:
        img_8bit = (img_array * 255).astype('uint8')
        img = Image.fromarray(img_8bit)
        img = img.resize(target_size)
        img_array = np.array(img)
        return np.expand_dims(img_array, axis=0) / 255.0
    except Exception as e:
        print(f"Error preparing image: {str(e)}")
        raise

def save_updated_dicom(original_ds, prediction):
    """Create new DICOM file with prediction metadata"""
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = original_ds.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = original_ds.SOPInstanceUID
    file_meta.ImplementationClassUID = "1.2.3.4"

    new_ds = FileDataset(original_ds.filename, {},
                         file_meta=file_meta,
                         preamble=original_ds.preamble)

    for elem in original_ds:
        new_ds.add(elem)

    new_ds.add_new([0x0009, 0x1001], "LO", CLASS_LABELS[prediction])
    new_ds.add_new([0x0009, 0x1003], "DA", datetime.datetime.now().strftime("%Y%m%d"))

    return new_ds

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preview', methods=['POST'])
def preview():
    clear_uploads_folder()

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            img_array, _ = dicom_to_array(filepath)
            img_pil = Image.fromarray((img_array * 255).astype('uint8'))

            img_byte_arr = io.BytesIO()
            img_pil.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            return img_byte_arr, 200, {'Content-Type': 'image/png'}
        except Exception as e:
            return jsonify({'error': f'DICOM processing failed: {str(e)}'}), 400
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    else:
        return jsonify({'error': 'Only DICOM (.dcm) files allowed'}), 400

@app.route('/predict', methods=['POST'])
def predict():
    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'predicted_' + filename)
        file.save(filepath)

        try:
            img_array, original_ds = dicom_to_array(filepath)
            processed_image = prepare_image(img_array, (256, 256))
            predictions = model.predict(processed_image)

            predicted_class = 1 if predictions[0][0] > 0.5 else 0
            confidence = float(abs(predictions[0][0] - .5) * 2)

            updated_ds = save_updated_dicom(original_ds, predicted_class)
            updated_ds.save_as(output_path)

            return jsonify({
                'prediction': CLASS_LABELS[predicted_class],
                'confidence': confidence,
                'download_url': f'/download/{filename}'
            })
        except Exception as e:
            return jsonify({'error': f'Prediction failed: {str(e)}'}), 400
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    else:
        return jsonify({'error': 'Only DICOM (.dcm) files allowed'}), 400

@app.route('/download/<filename>')
def download(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'predicted_' + secure_filename(filename))
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
