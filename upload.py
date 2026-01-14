import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import PdfHistory
from extensions import db
from pdf_extract import extract_font_segments, str_to_latex  



def generate_latex(segments):
    """Generate LaTeX from segments using your existing str_to_latex function"""
    return str_to_latex(segments)

def escape_latex(text):
    """Escape LaTeX special characters"""
    if not text:
        return ""
    
    replacements = {
        '\\': '\\textbackslash{}',
        '{': '\\{',
        '}': '\\}',
        '$': '\\$',
        '&': '\\&',
        '%': '\\%',
        '#': '\\#',
        '^': '\\textasciicircum{}',
        '_': '\\_',
        '~': '\\textasciitilde{}'
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text

upload_bp = Blueprint('upload', __name__, url_prefix='/upload')

@upload_bp.route('/')
@login_required
def index():
    history = PdfHistory.query.filter_by(user_id=current_user.id).order_by(PdfHistory.created_at.desc()).all()
    return render_template('index.html', user=current_user.username, history=history)

@upload_bp.route('/file', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        flash('Invalid file type', 'danger')
        return redirect(url_for('upload.index'))

    filename = secure_filename(file.filename)
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    file.save(save_path)
    
    # Process the PDF
    try:
        segments = extract_font_segments(save_path)
        json_filename = filename.replace('.pdf', '.json')
        json_path = os.path.join(current_app.config['UPLOAD_FOLDER'], json_filename)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        
        # Store processing result in database
        new_entry = PdfHistory(
            user_id=current_user.id,
            filename=filename,
            json_path=json_filename
        )
        
        # Delete oldest if more than 5 entries
        history = PdfHistory.query.filter_by(user_id=current_user.id).order_by(PdfHistory.created_at).all()
        db.session.add(new_entry)
        db.session.commit()
        
        flash('PDF processed successfully!', 'success')
        return redirect(url_for('upload.view_results', filename=json_filename))
        
    except Exception as e:
        current_app.logger.error(f"Error processing PDF: {str(e)}")
        flash('Error processing PDF', 'danger')
        return redirect(url_for('upload.index'))

@upload_bp.route('/results/<filename>')
@login_required
def view_results(filename):
    """View processing results for a specific PDF"""
    try:
        # Verify the file belongs to the current user
        history_entry = PdfHistory.query.filter_by(
            user_id=current_user.id,
            json_path=filename
        ).first()
        
        if not history_entry:
            flash('File not found or access denied', 'danger')
            return redirect(url_for('upload.index'))
        
        # Load the JSON data
        json_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(json_path):
            flash('Results file not found', 'danger')
            return redirect(url_for('upload.index'))
        
        with open(json_path, 'r', encoding='utf-8') as f:
            segments = json.load(f)
        
        # Categorize segments by font size (matching your original logic)
        structure = {
            'newsession': [],  # Large fonts (28pt equivalent)
            'subsession': [],  # Medium fonts (18pt equivalent) 
            'content': []      # Regular fonts (12pt equivalent)
        }
        
        for segment in segments:
            size = segment.get('size', 12)
            text = segment.get('text', '').strip()
            
            if not text or text.isspace():
                continue
            
            # Find closest font size to target sizes
            target_sizes = [28, 18, 12]
            closest_size = min(target_sizes, key=lambda x: abs(x - size))
            
            if closest_size == 28:
                structure['newsession'].append(text)
            elif closest_size == 18:
                structure['subsession'].append(text)
            elif closest_size == 12:
                structure['content'].append(text)
        
        return render_template('results.html', 
                             filename=history_entry.filename,
                             structure=structure,
                             segments=segments,
                             user=current_user.username)
        
    except Exception as e:
        current_app.logger.error(f"Error viewing results: {str(e)}")
        flash('Error loading results', 'danger')
        return redirect(url_for('upload.index'))

@upload_bp.route('/generate-latex/<filename>')
@login_required
def generate_latex_route(filename):
    """Generate LaTeX from processed PDF data"""
    try:
        # Verify the file belongs to the current user
        history_entry = PdfHistory.query.filter_by(
            user_id=current_user.id,
            json_path=filename
        ).first()
        
        if not history_entry:
            return jsonify({'error': 'File not found or access denied'}), 404
        
        # Load the JSON data
        json_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(json_path):
            return jsonify({'error': 'Results file not found'}), 404
        
        with open(json_path, 'r', encoding='utf-8') as f:
            segments = json.load(f)
        
        # Generate LaTeX using your existing function
        latex_content = generate_latex(segments)
        
        return jsonify({
            'latex': latex_content,
            'filename': history_entry.filename.replace('.pdf', '.tex')
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generating LaTeX: {str(e)}")
        return jsonify({'error': 'Error generating LaTeX'}), 500

@upload_bp.route('/delete/<int:history_id>')
@login_required
def delete_file(history_id):
    """Delete a processed file"""
    try:
        # Find the history entry belonging to current user
        history_entry = PdfHistory.query.filter_by(
            id=history_id,
            user_id=current_user.id
        ).first()
        
        if not history_entry:
            flash('File not found', 'danger')
            return redirect(url_for('upload.index'))
        
        # Delete the JSON file
        json_path = os.path.join(current_app.config['UPLOAD_FOLDER'], history_entry.json_path)
        if os.path.exists(json_path):
            os.remove(json_path)
        
        # Delete the original PDF file
        pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], history_entry.filename)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        # Delete from database
        db.session.delete(history_entry)
        db.session.commit()
        
        flash('File deleted successfully', 'success')
        return redirect(url_for('upload.index'))
        
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {str(e)}")
        flash('Error deleting file', 'danger')
        return redirect(url_for('upload.index'))
    
@upload_bp.route('/generate-latex/<filename>', methods=['POST'])
@login_required
def generate_latex(filename):
    # Get custom thresholds from form
    section_threshold = float(request.form.get('section_threshold', 28))
    subsection_threshold = float(request.form.get('subsection_threshold', 18))
    content_threshold = float(request.form.get('content_threshold', 12))
    
    # Get the PDF path
    pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(pdf_path):
        flash('PDF file not found', 'danger')
        return redirect(url_for('upload.index'))
    
    try:
        # Extract font segments
        segments = extract_font_segments(pdf_path)
        
        # Convert to LaTeX
        latex_code = str_to_latex(
            segments,
            section_threshold=section_threshold,
            subsection_threshold=subsection_threshold,
            content_threshold=content_threshold
        )
        
        # Create a complete LaTeX document
        full_latex = (
            "\\documentclass{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{amsmath}\n"
            "\\usepackage{amssymb}\n"
            "\\begin{document}\n\n" +
            latex_code +
            "\n\\end{document}"
        )
        
        # Save to a file
        tex_filename = filename.replace('.pdf', '.tex')
        tex_path = os.path.join(current_app.config['UPLOAD_FOLDER'], tex_filename)
        
        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(full_latex)
        
        # Store in database
        pdf_entry = PdfHistory.query.filter_by(filename=filename, user_id=current_user.id).first()
        if pdf_entry:
            pdf_entry.latex_path = tex_filename
            db.session.commit()
        
        # Redirect to preview page
        return redirect(url_for('upload.latex_preview', filename=tex_filename))
        
    except Exception as e:
        current_app.logger.error(f"Error generating LaTeX: {str(e)}")
        flash('Error generating LaTeX code', 'danger')
        return redirect(url_for('upload.view_results', filename=filename.replace('.pdf', '.json')))

@upload_bp.route('/latex-preview/<filename>')
@login_required
def latex_preview(filename):
    tex_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(tex_path):
        flash('LaTeX file not found', 'danger')
        return redirect(url_for('upload.index'))
    
    try:
        with open(tex_path, 'r', encoding='utf-8') as f:
            latex_content = f.read()
        
        return render_template('latex_preview.html', 
                              filename=filename,
                              pdf_filename=filename.replace('.tex', '.pdf'),
                              latex_content=latex_content)
        
    except Exception as e:
        current_app.logger.error(f"Error loading LaTeX: {str(e)}")
        flash('Error loading LaTeX content', 'danger')
        return redirect(url_for('upload.index'))

@upload_bp.route('/download-latex/<filename>')
@login_required
def download_latex(filename):
    tex_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    return send_file(tex_path, as_attachment=True)

@upload_bp.route('/history')
@login_required
def history():
    # Get all history entries for the current user
    history = PdfHistory.query.filter_by(user_id=current_user.id).order_by(PdfHistory.created_at.desc()).all()
    return render_template('history.html', history=history)

#@upload_bp.route('/delete-entry/<int:entry_id>', methods=['POST'])
#@login_required
def delete_entry(entry_id):
    entry = PdfHistory.query.get_or_404(entry_id)
    
    # Verify ownership
    if entry.user_id != current_user.id:
        flash('You do not have permission to delete this entry', 'danger')
        return redirect(url_for('upload.history'))
    
    try:
        # Delete associated files
        files_to_delete = []
        
        if entry.filename:
            pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], entry.filename)
            if os.path.exists(pdf_path):
                files_to_delete.append(pdf_path)
        
        if entry.json_path:
            json_path = os.path.join(current_app.config['UPLOAD_FOLDER'], entry.json_path)
            if os.path.exists(json_path):
                files_to_delete.append(json_path)
        
        if entry.latex_path:
            latex_path = os.path.join(current_app.config['UPLOAD_FOLDER'], entry.latex_path)
            if os.path.exists(latex_path):
                files_to_delete.append(latex_path)
        
        # Delete files
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
            except Exception as e:
                current_app.logger.error(f"Error deleting file {file_path}: {str(e)}")
        
        # Delete database entry
        db.session.delete(entry)
        db.session.commit()
        
        flash('Entry deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting entry: {str(e)}")
        flash('Error deleting entry', 'danger')
    
    return redirect(url_for('upload.history'))



@upload_bp.route('/history')
@login_required
def view_history():
    history = PdfHistory.query.filter_by(user_id=current_user.id).order_by(PdfHistory.created_at.desc()).all()
    return render_template('history.html', history=history)



@upload_bp.route('/download-pdf/<filename>')
@login_required
def download_pdf(filename):
    pdf_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    # Verify ownership
    entry = PdfHistory.query.filter_by(filename=filename, user_id=current_user.id).first()
    if not entry:
        flash('File not found or you do not have permission', 'danger')
        return redirect(url_for('upload.history'))
    
    if not os.path.exists(pdf_path):
        flash('PDF file not found', 'danger')
        return redirect(url_for('upload.history'))
    
    return send_file(pdf_path, as_attachment=True)

@upload_bp.route('/delete_pdf', methods=['POST'])
@login_required
def delete_pdf():
    pdf_id = request.form.get('pdf_id')
    
    if not pdf_id:
        flash('Invalid request', 'error')
        return redirect(url_for('upload.history'))  # or wherever you want to redirect
    
    try:
        # Find the PDF record
        pdf_record = PdfHistory.query.filter_by(id=pdf_id, user_id=current_user.id).first()
        
        if not pdf_record:
            flash('File not found or you do not have permission to delete it', 'error')
            return redirect(url_for('upload.history'))
        
        # Delete the actual files if they exist
        import os
        if pdf_record.json_path and os.path.exists(pdf_record.json_path):
            os.remove(pdf_record.json_path)
        
        # You might also want to delete the original PDF file if you store it
            if os.path.exists(pdf_record.pdf_path):
                os.remove(pdf_record.pdf_path)
        
        # Delete from database
        db.session.delete(pdf_record)
        db.session.commit()
        
        flash('File deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error deleting file', 'error')
        print(f"Error deleting PDF: {e}")  # For debugging
    
    return redirect(url_for('upload.history'))  # Redirect back to history page
