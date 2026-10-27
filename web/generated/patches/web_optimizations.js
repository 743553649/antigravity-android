(function(){
/**
 * patches/web_optimizations/taps.js - kill the 300ms double-tap delay.
 */
'use strict';

function installTaps(doc) {
  try {
    var style = doc.createElement('style');
    style.setAttribute('data-agy', 'web-optimizations');
    style.textContent =
      'button,a,[role="button"],input,select,textarea{touch-action:manipulation;}';
    (doc.head || doc.documentElement).appendChild(style);
  } catch (e) {}
}

/**
 * patches/web_optimizations/viewport.js - keep --agy-vvh honest while the
 * soft keyboard opens.
 */
function installViewport(global, doc) {
  try {
    if (global.visualViewport) {
      global.visualViewport.addEventListener('resize', function () {
        var vv = global.visualViewport;
        if (vv && vv.height && doc.documentElement) {
          doc.documentElement.style.setProperty(
            '--agy-vvh', Math.round(vv.height) + 'px');
        }
      }, { passive: true });
    }
  } catch (e) {}
}

/**
 * patches/web_optimizations/gpu.js - GPU-accelerate scroll/animation surfaces
 * and isolate layout for lists.
 */
function installGpu(doc) {
  try {
    if (!doc.querySelector('style[data-agy="gpu-acceleration"]')) {
      var gpu = doc.createElement('style');
      gpu.setAttribute('data-agy', 'gpu-acceleration');
      // Promote ONLY the real scroll containers. Never inline <code>/<pre>:
      // per-element layers explode on Mali and saturate RenderThread.
      gpu.textContent =
        'main, [data-testid="chat-container"], .scrollable {' +
        ' transform: translateZ(0);' +
        ' -webkit-overflow-scrolling: touch; }' +
        '[role="listitem"], .message-row, .artifact-viewer {' +
        ' contain: layout style; }' +
        '*{ -webkit-tap-highlight-color: transparent; }';
      (doc.head || doc.documentElement).appendChild(gpu);
    }
  } catch (e) {}
}

/**
 * patches/web_optimizations/resume_sync.js - sync trajectory streams on app resume.
 *
 * When the user switches away from Antigravity while an AI task is executing, Android
 * freezes the WebView renderer and throttles network buffers. The background Go server
 * and language_server continue running full speed under Partial WakeLock, but the WebView's
 * active ConnectRPC stream stalls.
 *
 * This patch listens for 'agy:host-resume', 'visibilitychange' (when visible), and 'focus',
 * and invokes window.__agRefreshTrajectories() after a brief 120ms stabilization window.
 * This disposes any dead/stalled stream and re-links to a fresh stream from language_server,
 * instantly catching up all steps, tool calls, and content generated while in the background.
 */
'use strict';

function installResumeSync(global) {
  var lastSyncTime = 0;

  function doSync(source) {
    var now = Date.now();
    if (now - lastSyncTime < 500) return; // debounce rapid triggers
    lastSyncTime = now;

    setTimeout(function () {
      try {
        if (typeof global.__agRefreshTrajectories === 'function') {
          global.__agRefreshTrajectories(source);
        } else if (global.__agTrajectoriesRegistry && typeof global.__agTrajectoriesRegistry.setFactory === 'function') {
          console.log('[AGY ResumeSync] Refreshing active trajectories triggered by ' + source);
          var reg = global.__agTrajectoriesRegistry;
          if (reg._factory) {
            reg.setFactory(reg._factory);
          }
        }
      } catch (err) {
        console.warn('[AGY ResumeSync] Failed to refresh trajectories:', err);
      }
    }, 120);
  }

  // 1. Android native host-resume broadcast
  global.addEventListener('agy:host-resume', function () {
    doSync('agy:host-resume');
  }, { passive: true });

  // 2. Browser document visibility change
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden && document.visibilityState === 'visible') {
        doSync('visibilitychange');
      }
    }, { passive: true });
  }

  // 3. Window focus
  global.addEventListener('focus', function () {
    doSync('window:focus');
  }, { passive: true });

  global.__agResumeSync = {
    installed: true,
    syncNow: function () { doSync('manual'); }
  };
}

/**
 * patches/web_optimizations/public-api.js - install and expose.
 */
var global = window;

if (global.__AG_WEB_OPTIMIZATIONS__) return;
global.__AG_WEB_OPTIMIZATIONS__ = true;

var doc = global.document;
if (!doc) return;

installTaps(doc);
installViewport(global, doc);
installGpu(doc);
installResumeSync(global);

global.__agWebOptimizations = { installed: true };


})();
