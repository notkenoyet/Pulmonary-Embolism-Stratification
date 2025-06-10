$(document).ready(function() {
  const $fileInput = $('#file-upload');
  const $predictBtn = $('#predict-btn');
  const $downloadBtn = $('#download-btn');
  const $imagePreview = $('#image-preview');
  const $errorMessage = $('#error-message');
  const $results = $('#results');
  const $fileInfo = $('#file-info');

  let currentFilename = '';

  $imagePreview.on('load', function() {
  $('#predict-btn').addClass('visible');
  });

  $fileInput.on('change', function() {
    $('#predict-btn').removeClass('visible');
    $errorMessage.text('');
    $results.hide();
    $downloadBtn.hide();

    const file = this.files[0];

    if (file) {
      currentFilename = file.name;
      $fileInfo.text(`Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);

      if (!file.name.toLowerCase().endsWith('.dcm')) {
        $errorMessage.text('Please select a DICOM (.dcm) file');
        $imagePreview.hide();
        $predictBtn.hide();
        return;
      }

      const formData = new FormData();
      formData.append('file', file);

      $.ajax({
        url: '/preview',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        xhrFields: {
          responseType: 'blob'
        },
        success: function(imageBlob) {
          const imageUrl = URL.createObjectURL(imageBlob);
          $imagePreview.attr('src', imageUrl).show();
          $predictBtn.show();
        },
        error: function(xhr) {
          const error = xhr.responseJSON?.error || 'Preview generation failed';
          $errorMessage.text(error);
          $imagePreview.hide();
          $predictBtn.hide();
        }
      });
    } else {
      $fileInfo.text('No file selected');
      $imagePreview.hide();
      $predictBtn.hide();
    }
  });

  $predictBtn.on('click', function() {
    const file = $fileInput[0].files[0];
    const formData = new FormData();
    formData.append('file', file);

    $predictBtn.prop('disabled', true).text('Analyzing...');
    $errorMessage.text('');

    $.ajax({
      url: '/predict',
      type: 'POST',
      data: formData,
      processData: false,
      contentType: false,
      success: function(response) {
        $('#prediction-class').text(response.prediction);
        $('#prediction-confidence').text((response.confidence * 100).toFixed(2) + '%');
        $results.show();

        $downloadBtn.attr('href', response.download_url).show();
      },
      error: function(xhr) {
        const error = xhr.responseJSON?.error || 'Analysis failed';
        $errorMessage.text(error);
      },
      complete: function() {
        $predictBtn.prop('disabled', false).text('Analyze Image');
      }
    });
  });
});
