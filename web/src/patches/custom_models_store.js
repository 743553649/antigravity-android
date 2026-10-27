(function () {
  'use strict';

  var STORAGE_KEY = 'ag_native_custom_models';

  function sanitizeModelsMap(models) {
    if (!models || typeof models !== 'object') return {};
    var changed = false;
    Object.keys(models).forEach(function (label) {
      var item = models[label];
      if (!item || typeof item !== 'object') return;
      var info = item.modelInfo || {};
      var mName = info.modelName || label;
      var baseUrl = (item.baseUrl || '').trim();

      // Recover URL if user previously put URL in modelName while baseUrl was default
      if ((mName.indexOf('http://') === 0 || mName.indexOf('https://') === 0) &&
          (!baseUrl || baseUrl === 'https://api.deepseek.com/v1')) {
        baseUrl = mName.trim();
        item.baseUrl = baseUrl;
        changed = true;
      }

      // Clean modelName if it was a URL or gemini-api scheme
      if (mName.indexOf('http://') === 0 || mName.indexOf('https://') === 0 || mName.indexOf('gemini-api:') === 0) {
        info.modelName = info.chatModelName || label;
        changed = true;
      }

      // Auto-heal stale default baseUrl for AI Ping models (e.g. DeepSeek-V4.1-Flash-1017)
      if ((!baseUrl || baseUrl === 'https://api.deepseek.com/v1') &&
          (label.indexOf('V4') !== -1 || label.indexOf('1017') !== -1 || (info.modelName || '').indexOf('1017') !== -1)) {
        item.baseUrl = 'https://aiping.cn/api/v1';
        changed = true;
      }
    });
    if (changed) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(models));
      } catch (_) {}
    }
    return models;
  }

  function syncToNative(jsonStr, modelsObj) {
    try {
      if (window.Android && typeof window.Android.saveCustomModels === 'function') {
        window.Android.saveCustomModels(jsonStr);
      }
    } catch (_) {}

    try {
      var gw = (window.__APP_CONFIG__ && window.__APP_CONFIG__.gatewayPort) || 47160;
      fetch('http://127.0.0.1:' + gw + '/gateway', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'save_custom_models', payload: modelsObj || JSON.parse(jsonStr) })
      }).catch(function () {});
    } catch (_) {}
  }

  function loadModels() {
    try {
      var s = localStorage.getItem(STORAGE_KEY);
      if (s && s !== '{}') {
        var parsedLocal = sanitizeModelsMap(JSON.parse(s));
        var cleanStr = JSON.stringify(parsedLocal);
        syncToNative(cleanStr, parsedLocal);
        return parsedLocal;
      }
      if (window.Android && typeof window.Android.getCustomModels === 'function') {
        var nativeStr = window.Android.getCustomModels();
        if (nativeStr && nativeStr !== '{}') {
          var parsed = sanitizeModelsMap(JSON.parse(nativeStr));
          var cleanNativeStr = JSON.stringify(parsed);
          localStorage.setItem(STORAGE_KEY, cleanNativeStr);
          syncToNative(cleanNativeStr, parsed);
          return parsed;
        }
      }
      return {};
    } catch (_) {
      return {};
    }
  }

  function saveModels(models) {
    var clean = sanitizeModelsMap(models);
    var jsonStr = JSON.stringify(clean);
    try {
      localStorage.setItem(STORAGE_KEY, jsonStr);
    } catch (_) {}
    syncToNative(jsonStr, clean);
    try {
      window.dispatchEvent(new CustomEvent('ag-custom-models-changed', { detail: clean }));
    } catch (_) {}
  }

  // Preload and sync on script execution
  loadModels();

  window.__agCustomModelsStore = {
    getModels: loadModels,
    saveModels: saveModels,
    addModel: function (label, modelInfo, apiKey, baseUrl, oldLabel) {
      var m = loadModels();
      if (oldLabel && oldLabel !== label && m[oldLabel]) {
        delete m[oldLabel];
      }
      var cleanUrl = (baseUrl || '').trim().replace(/\/+$/, '').replace(/\/chat\/completions$/, '');
      if (!cleanUrl) cleanUrl = 'https://aiping.cn/api/v1';
      m[label] = {
        modelInfo: modelInfo,
        apiKey: (apiKey || '').trim(),
        baseUrl: cleanUrl
      };
      saveModels(m);
      return m;
    },
    removeModel: function (label) {
      var m = loadModels();
      delete m[label];
      saveModels(m);
      return m;
    },
    testModel: function (baseUrl, apiKey, modelName) {
      try {
        if (window.Android && typeof window.Android.testCustomModel === 'function') {
          return window.Android.testCustomModel(baseUrl || '', apiKey || '', modelName || '');
        }
      } catch (e) {
        return 'ERR:' + (e && e.message ? e.message : String(e));
      }
      return 'ERR:当前环境不支持原生连接测试';
    }
  };
})();
