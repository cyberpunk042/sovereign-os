(function () {
  'use strict';
  var message = document.getElementById('warp-render-message');
  var figure = document.getElementById('warp-render-figure');
  var image = document.getElementById('warp-render-image');
  var caption = document.getElementById('warp-render-caption');
  var download = document.getElementById('warp-render-download');
  var timer, generation = 0;
  function refresh(reveal) {
    var current = ++generation;
    fetch('/api/control/warp-render-result', {cache: 'no-store'}).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    }).then(function (data) {
      if (current !== generation) return;
      var result = data.latest_render;
      if (!result || !/^data:image\/png;base64,/.test(result.image_url || '')) {
        message.textContent = reveal ? 'Render finished, but no preview was published. Check the render output.' : 'No saved render yet. Choose a scene and click Render.';
        return;
      }
      image.src = result.image_url;
      image.alt = 'Rendered scene: ' + result.scene;
      caption.textContent = result.scene + ' · ' + new Date(result.created_at).toLocaleString() + ' · ' + Math.round(result.bytes / 1024) + ' KB';
      download.href = result.image_url;
      download.download = result.filename;
      figure.hidden = false;
      message.textContent = 'Rendered successfully: ' + result.scene;
      if (reveal) document.getElementById('warp-render-result').scrollIntoView({behavior:'smooth', block:'start'});
    }).catch(function () { message.textContent = 'Cannot load the render preview. Your saved image has not been deleted.'; });
  }
  image.addEventListener('error', function () { message.textContent = 'The saved render could not be displayed.'; });
  new MutationObserver(function (changes) {
    changes.forEach(function (change) {
      var node = change.target.nodeType === 1 ? change.target : change.target.parentElement;
      var result = node && node.closest('.cs-result, .so-exec-result');
      if (!result || !/applied.*warp-render/.test(result.textContent)) return;
      clearTimeout(timer);
      timer = setTimeout(function () { refresh(true); }, 100);
    });
  }).observe(document.body, {subtree:true, childList:true, characterData:true});
  refresh(false);
})();
