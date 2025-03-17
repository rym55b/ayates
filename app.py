import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import subprocess
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_file, flash

app = Flask(__name__)
app.secret_key = "votre_clé_secrète"  # Nécessaire pour les messages flash
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['VIDEO_FOLDER'] = 'videos'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16MB pour les uploads

# Créer les dossiers nécessaires s'ils n'existent pas
for folder in [app.config['UPLOAD_FOLDER'], app.config['VIDEO_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# Paramètres de la vidéo
WIDTH, HEIGHT = 1280, 720
TEXT_COLOR = (255, 255, 255)  # Texte blanc
FONT_PATH = "static/fonts/Amiri-Regular.ttf"  # Police arabe
FONT_SIZE = 60
FPS = 30
WORD_DELAY = 20

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create-video', methods=['POST'])
def create_video():
    if 'audio' not in request.files or 'text' not in request.form:
        flash('Fichiers manquants')
        return redirect(request.url)
    
    audio_file = request.files['audio']
    text = request.form['text']
    
    if audio_file.filename == '':
        flash('Aucun fichier audio sélectionné')
        return redirect(request.url)
    
    # Générer des noms de fichiers uniques
    session_id = str(uuid.uuid4())
    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_audio.mp3")
    text_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_text.txt")
    temp_video = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_temp.mp4")
    output_video = os.path.join(app.config['VIDEO_FOLDER'], f"{session_id}_output.mp4")
    
    # Sauvegarder les fichiers
    audio_file.save(audio_path)
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    try:
        # Charger la police
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        
        # Initialiser la vidéo
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(temp_video, fourcc, FPS, (WIDTH, HEIGHT))
        
        # Générer la vidéo avec le texte
        verses = text.strip().split("\n")
        for verse in verses:
            reshaped_text = arabic_reshaper.reshape(verse)
            bidi_text = get_display(reshaped_text)
            words = bidi_text.split()
            displayed_text = ""
            
            # Position pour le texte arabe (RTL)
            x_position = WIDTH - 50
            y_position = HEIGHT // 2
            
            for word in words:
                displayed_text = word + " " + displayed_text
                
                for _ in range(WORD_DELAY):
                    img = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
                    img_pil = Image.fromarray(img)
                    draw = ImageDraw.Draw(img_pil)
                    
                    # Calculer la largeur du texte pour l'alignement
                    text_width, _ = draw.textsize(displayed_text, font=font)
                    text_position = (x_position - text_width, y_position)
                    
                    draw.text(text_position, displayed_text, font=font, fill=TEXT_COLOR)
                    
                    frame = np.array(img_pil)
                    video_writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        
        # Fermer la vidéo
        video_writer.release()
        
        # Ajouter l'audio avec FFmpeg
        cmd = [
            "ffmpeg", "-i", temp_video, 
            "-i", audio_path, 
            "-c:v", "libx264", 
            "-c:a", "aac", 
            "-b:a", "192k", 
            "-shortest", 
            "-y",
            output_video
        ]
        subprocess.run(cmd, check=True)
        
        # Nettoyer les fichiers temporaires
        for file in [audio_path, text_path, temp_video]:
            if os.path.exists(file):
                os.remove(file)
        
        # Rediriger vers la page de téléchargement
        return redirect(url_for('download_video', video_id=session_id))
    
    except Exception as e:
        flash(f'Erreur lors de la création de la vidéo: {str(e)}')
        return redirect(url_for('index'))

@app.route('/download/<video_id>')
def download_video(video_id):
    video_path = os.path.join(app.config['VIDEO_FOLDER'], f"{video_id}_output.mp4")
    if os.path.exists(video_path):
        return render_template('download.html', video_id=video_id)
    else:
        flash('Vidéo non trouvée')
        return redirect(url_for('index'))

@app.route('/get-video/<video_id>')
def get_video(video_id):
    video_path = os.path.join(app.config['VIDEO_FOLDER'], f"{video_id}_output.mp4")
    return send_file(video_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
