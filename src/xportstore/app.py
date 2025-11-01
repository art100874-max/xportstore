import toga
from toga.style import Pack
from toga.style.pack import COLUMN

MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 5) "
             "AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/124.0.0.0 Mobile Safari/537.36")

INJECT_JS = r"""
(function() {
  try {
    // 0) helper: извлечь url(...) из CSS
    function extractUrl(val) {
      if (!val) return null;
      var m = val.match(/url\((['"]?)(.*?)\1\)/i);
      return m && m[2] ? m[2] : null;
    }

    // 1) <img>: переносим data-* в src, поднимаем из <picture>/<source>
    var imgs = document.querySelectorAll('img');
    imgs.forEach(function(img) {
      var cand = img.getAttribute('data-src') || img.getAttribute('data-original') || img.getAttribute('data-lazy');
      if (cand && !img.getAttribute('src')) img.setAttribute('src', cand);

      if (!img.getAttribute('src')) {
        var pic = img.closest('picture');
        if (pic) {
          var srcset = pic.querySelector('source[srcset]');
          if (srcset) {
            var first = (srcset.getAttribute('srcset') || '').split(',')[0].trim().split(' ')[0];
            if (first) img.setAttribute('src', first);
          }
        }
      }

      img.loading = 'eager';
      img.decoding = 'sync';
      img.removeAttribute('data-src');
      img.removeAttribute('data-original');
      img.removeAttribute('data-lazy');
    });

    // 2) элементы с фонами: превращаем background-image в <img>
    var bgElems = document.querySelectorAll('[style*="background"], .bg, .lazybg, .lazy-bg, .category-icon, .menu-icon');
    bgElems.forEach(function(el) {
      var style = window.getComputedStyle(el);
      var url = extractUrl(style.backgroundImage);
      if (!url) return;
      // Если внутри уже есть <img> с таким src — не плодим
      var has = el.querySelector('img[data-from-bg="1"]');
      if (has && (has.getAttribute('src') === url)) return;

      var im = new Image();
      im.setAttribute('data-from-bg', '1');
      im.loading = 'eager';
      im.decoding = 'sync';
      im.alt = '';
      im.style.maxWidth = '100%';
      im.style.maxHeight = '100%';
      im.style.display = 'block';
      im.style.objectFit = 'contain';
      im.src = url;

      // вставляем как первый ребёнок
      el.insertBefore(im, el.firstChild);
    });

    // 3) даём «пинок» lazy-скриптам
    window.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('resize'));

    // 4) повторяем через 600 и 1200 мс на случай поздней инициализации
    setTimeout(function(){
      window.dispatchEvent(new Event('scroll'));
      window.dispatchEvent(new Event('resize'));
      (typeof lazySizes !== 'undefined' && lazySizes.loader && lazySizes.loader.checkElems && lazySizes.loader.checkElems());
    }, 600);

    setTimeout(function(){
      window.dispatchEvent(new Event('scroll'));
      window.dispatchEvent(new Event('resize'));
      (typeof lazySizes !== 'undefined' && lazySizes.loader && lazySizes.loader.checkElems && lazySizes.loader.checkElems());
    }, 1200);
  } catch(e) { console.log('inject error', e); }
})();
"""

class XportStore(toga.App):
    def startup(self):
        box = toga.Box(style=Pack(direction=COLUMN))

        # Через http, чтобы НИ ОДНА картинка не блокировалась
        self.web = toga.WebView(style=Pack(flex=1), url="http://xportstore.ru/")
        box.add(self.web)

        self.main_window = toga.MainWindow(title="XPort Store")
        self.main_window.content = box
        self.main_window.show()

        # --- Android настройки WebView + инъекция JS + обработка "Назад"
        try:
            native = self.web._impl.native
            settings = native.getSettings()
            settings.setMixedContentMode(0)  # ALWAYS_ALLOW
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setLoadsImagesAutomatically(True)
            settings.setBlockNetworkImage(False)
            settings.setAllowFileAccess(True)
            settings.setAllowContentAccess(True)
            settings.setUserAgentString(MOBILE_UA)

            # Разрешим отладку webview (chrome://inspect)
            from android.webkit import WebView as _WV
            _WV.setWebContentsDebuggingEnabled(True)

            # Внедряем JS после загрузки страницы (и при навигации внутри)
            from android.webkit import WebViewClient
            class HookClient(WebViewClient):
                def onPageFinished(self, view, url):
                    try:
                        view.evaluateJavascript(INJECT_JS, None)
                        # повтор через 800 мс
                        view.postDelayed(lambda: view.evaluateJavascript(INJECT_JS, None), 800)
                    except Exception as e:
                        print("eval js err", e)
            native.setWebViewClient(HookClient())

            # "Назад" = история (на случай если Activity-хук не сработает)
            from android.view import KeyEvent
            def on_key(v, keyCode, event):
                if keyCode == KeyEvent.KEYCODE_BACK and event.getAction() == KeyEvent.ACTION_UP:
                    if native.canGoBack():
                        native.goBack()
                        return True
                return False
            native.setOnKeyListener(on_key)
            native.setFocusableInTouchMode(True)
            native.requestFocus()

            # Помечаем WebView, чтобы дубль-обработчик в Activity тоже сработал
            native.setTag("MAIN_WEBVIEW")

        except Exception as e:
            print("Android tuning skipped:", e)

def main():
    return XportStore(
        "XPort Store",
        "ru.xportstore",
        author="X-Port",
        home_page="https://xportstore.ru",
    )
