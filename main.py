import shutil
from threading import Timer
from flask import Flask, request, send_file, render_template, render_template_string, jsonify
import os
import zipfile
from io import BytesIO
import threading
import time  # Используется для имитации длительной обработки
import random
from PIL import Image
import os


def convert_collages_to_pdf(output_folder):
    for root, dirs, files in os.walk(output_folder):
        collage_files = [os.path.join(root, file) for file in files if file.endswith('.jpg')]

        if not collage_files:
            continue

        # Сортировка файлов, чтобы PDF был в правильном порядке
        collage_files.sort()

        # Создание PDF
        images = [Image.open(x) for x in collage_files]
        pdf_filename = os.path.join(root, "collage.pdf")
        images[0].save(pdf_filename, "PDF", resolution=100.0, save_all=True, append_images=images[1:])

        # Удаление исходных коллажей
        for collage_file in collage_files:
            os.remove(collage_file)


def create_collage(template, images, background_image, collage_size):
    background = Image.open(background_image).resize(collage_size)
    for idx, (x, y, w, h) in enumerate(template):
        if idx < len(images):
            img = Image.open(images[idx])
            target_size = (int(collage_size[0] * w), int(collage_size[1] * h))
            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            position = (int(collage_size[0] * x), int(collage_size[1] * y))
            background.paste(img, position, img if img.mode == 'RGBA' else None)
    return background


def get_all_images(folder):
    images = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(('jpg', 'jpeg', 'png')):
                images.append(os.path.join(root, file))
    return images


def create_collages(input_folder, background_images, collage_size, output_folder):
    templates = [
        [(0.1, 0.125, 0.75, 0.75), (0.7, 0, 0.2, 0.4), (0.7, 0.3, 0.2, 0.4), (0.7, 0.6, 0.2, 0.4)],
        [(0.1, 0, 0.5, 0.5), (0.6, 0, 0.5, 0.5), (0.1, 0.5, 0.5, 0.5), (0.6, 0.5, 0.5, 0.5)],
        [(0, 0.2, 0.33, 0.5), (0.4, 0, 0.34, 0.33), (0.7, 0.2, 0.33, 0.5), (0.4, 0.33, 0.34, 0.34),
         (0.4, 0.67, 0.34, 0.33)],
        [(0.2, 0, 0.3, 0.3), (0.5, 0, 0.3, 0.3), (0.8, 0, 0.3, 0.3), (0, 0.35, 0.3, 0.3), (0.7, 0.35, 0.3, 0.3),
         (0.2, 0.7, 0.3, 0.3), (0.5, 0.7, 0.3, 0.3), (0.8, 0.7, 0.3, 0.3), (0.35, 0.35, 0.3, 0.3)],
        [(0, 0, 0.5, 0.5), (0.6, 0, 0.5, 0.33), (0.5, 0.33, 0.25, 0.3), (0.75, 0.33, 0.25, 0.3), (0.5, 0.7, 0.25, 0.3),
         (0.75, 0.7, 0.25, 0.3), (0, 0.5, 0.5, 0.5)],

    ]
    for root, dirs, files in os.walk(input_folder):
        # Пропускаем папку, если в ней есть поддиректории
        if dirs:
            continue

        # Определение пути сохранения коллажей с учетом структуры папок
        relative_path = os.path.relpath(root, input_folder)
        output_collage_folder = os.path.join(output_folder, relative_path)

        images = [os.path.join(root, file) for file in files if file.endswith(('jpg', 'jpeg', 'png'))]
        images.sort()

        if not images:
            continue

        if not os.path.exists(output_collage_folder):
            os.makedirs(output_collage_folder)

        collage_index = 1
        while images:
            selected_template = random.choice(templates)
            num_images = len(selected_template)
            selected_images = images[:num_images]
            images = images[num_images:]

            selected_background = random.choice(background_images)
            collage = create_collage(selected_template, selected_images, selected_background, collage_size)

            collage_filename = f'collage_{collage_index}.jpg'
            collage_index += 1
            collage_path = os.path.join(output_collage_folder, collage_filename)
            collage.save(collage_path)


def create(input_folder='Input', output_folder='Output'):
    collage_size = (1600, 1600)
    background_images = ['подложка buybern.jpg']
    create_collages(input_folder, background_images, collage_size, output_folder)
    convert_collages_to_pdf(output_folder)


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['INPUT_FOLDER'] = 'Input'
app.config['OUTPUT_FOLDER'] = 'Output'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'zip'}


def process_files():
    create()

    # Упаковка результатов обработки в ZIP-архив
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(app.config['OUTPUT_FOLDER']):
            for file in files:
                zipf.write(os.path.join(root, file),
                           os.path.relpath(os.path.join(root, file),
                                           os.path.join(app.config['OUTPUT_FOLDER'], '..')))

    # Сохранение архива для последующей отправки пользователю
    with open('processed_files.zip', 'wb') as f:
        f.write(memory_file.getvalue())


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return 'No selected file or wrong file format', 400

    # Сохранение файла и его распаковка
    filename = file.filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(app.config['INPUT_FOLDER'])

    # Обнуляем флаг завершения обработки
    app.config['PROCESSING_COMPLETE'] = False
    # Запуск процесса обработки в отдельном потоке
    thread = threading.Thread(target=process_files)
    thread.start()

    return 'Файл успешно загружен. Подождите...'

@app.route('/status', methods=['GET'])
def status():
    file_exists = os.path.exists('processed_files.zip')
    return jsonify(processing_complete=file_exists)

@app.route('/download', methods=['GET'])
def download_file():
    if os.path.exists('processed_files.zip'):
        # Отправляем файл пользователю
        response = send_file('processed_files.zip', as_attachment=True)

        # Запускаем таймер для отложенного удаления файла и очистки папок
        timer = Timer(3.0, cleanup)  # Удаляем через 10 секунд
        timer.start()

        return response
    else:
        return 'Еще не завершено', 404

def cleanup():
    if os.path.exists('processed_files.zip'):
        os.remove('processed_files.zip')
    for folder in [app.config['INPUT_FOLDER'], app.config['OUTPUT_FOLDER']]:
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)

if __name__ == '__main__':
    # Создание папок, если они еще не существуют
    for folder in [app.config['UPLOAD_FOLDER'], app.config['INPUT_FOLDER'], app.config['OUTPUT_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
    app.run(debug=True)
