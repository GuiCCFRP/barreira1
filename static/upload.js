document.addEventListener('DOMContentLoaded', () => {
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const submitBtn = document.getElementById('submit-btn');
    
    
    let selectedFile = null;
    
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    
    dropArea.addEventListener('drop', handleDrop, false);
    
    
    fileInput.addEventListener('change', handleFiles);
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight() {
        dropArea.classList.add('highlight');
    }
    
    function unhighlight() {
        dropArea.classList.remove('highlight');
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        
        if (files.length > 0) {
            
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(files[0]);
            fileInput.files = dataTransfer.files;
            
            
            handleFiles({target: {files: files}});
        }
    }
    
    function handleFiles(e) {
        const files = e.target.files;
        
        if (files.length > 0) {
            const file = files[0];
            selectedFile = file;
            
            const isValidPDF = file.type === 'application/pdf' || 
                              file.name.toLowerCase().endsWith('.pdf');
            
            if (isValidPDF) {
                const fileName = sanitizeFilename(file.name);
                
                fileInfo.innerHTML = `
                    <div class="file-preview">
                        <i class="fas fa-file-pdf"></i>
                        <div class="file-details">
                            <span class="filename">${fileName}</span>
                            <span class="file-size">${formatFileSize(file.size)}</span>
                        </div>
                    </div>
                `;
                
                submitBtn.disabled = false;
                dropArea.classList.add('file-selected');
            } else {
                fileInfo.innerHTML = '<div class="error">Please select a PDF file</div>';
                submitBtn.disabled = true;
                selectedFile = null;
            }
        }
    }
    
    
    document.getElementById('upload-form').addEventListener('submit', function(e) {
        
        if (!fileInput.files || fileInput.files.length === 0) {
            e.preventDefault();
            alert('Please select a PDF file first');
            return false;
        }
        
        
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    });
    
    function sanitizeFilename(name) {
        return name.replace(/[^a-zA-Z0-9_.-]/g, '_');
    }
    
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
});