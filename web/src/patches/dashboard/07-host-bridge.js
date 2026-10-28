/**
 * patches/dashboard/07-host-bridge.js - 原生移动端 agPulseHost 驱动
 *
 * 为原版 1:1 前端挂件 (inline-widget.cjs / usage-ui.cjs) 提供标准宿主通信接口。
 * 直接利用本地内核的 LanguageServerService 提取真实配额、会话流速与上下文容量。
 */
'use strict';

// host bridge body
  var PREF_KEY = 'AntigravityPulse/preferences.json';

  // 读取持久化偏好设置（默认采用简体中文）
  function getStoredPreferences() {
    try {
      var raw = localStorage.getItem(PREF_KEY);
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    return {
      language: localStorage.getItem('ag-pulse-language') || 'zh-CN',
      group: localStorage.getItem('ag-pulse-group') || null,
      languageGuideDismissed: localStorage.getItem('ag-pulse-guide-dismissed') === 'true',
      usageGuideDismissed: localStorage.getItem('ag-pulse-usage-guide-dismissed') === 'true'
    };
  }

  // 保存偏好设置
  function saveStoredPreferences(input) {
    var cur = getStoredPreferences();
    var merged = Object.assign({}, cur, input || {});
    try {
      localStorage.setItem(PREF_KEY, JSON.stringify(merged));
      if (merged.language) localStorage.setItem('ag-pulse-language', merged.language);
      if (merged.group) localStorage.setItem('ag-pulse-group', merged.group);
      if (merged.languageGuideDismissed) localStorage.setItem('ag-pulse-guide-dismissed', 'true');
      if (merged.usageGuideDismissed) localStorage.setItem('ag-pulse-usage-guide-dismissed', 'true');
    } catch (_) {}
    return merged;
  }

  // 调用本地内核 ConnectRPC 接口（自动由 bridge.core.js 的 fetch-rewrite 转发与鉴权）
  async function callLanguageServer(method, payload) {
    var url = '/exa.language_server_pb.LanguageServerService/' + method;
    var res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Connect-Protocol-Version': '1'
      },
      body: JSON.stringify(payload || {})
    });
    if (!res.ok) {
      throw new Error('RPC ' + method + ' failed with HTTP ' + res.status);
    }
    return await res.json();
  }

  var quotaCache = null;
  var quotaCacheTime = 0;
  var quotaPending = null;

  // 刷新账户配额数据（5小时滚动额度 + 每周额度）
  async function fetchQuotaMetrics(force) {
    if (!force && quotaCache && (Date.now() - quotaCacheTime < 60000)) {
      return quotaCache;
    }
    if (quotaPending) return quotaPending;

    quotaPending = (async function () {
      try {
        var res = await callLanguageServer('RetrieveUserQuotaSummary', {});
        var parsed = quotaMetrics(res, Date.now());
        if (parsed && parsed.length) {
          quotaCache = parsed;
          quotaCacheTime = Date.now();
          return quotaCache;
        }
      } catch (e1) {
        // 回退调用 GetUserStatus
        try {
          var userRes = await callLanguageServer('GetUserStatus', {});
          var userParsed = quotaMetrics(userRes, Date.now());
          if (userParsed && userParsed.length) {
            quotaCache = userParsed;
            quotaCacheTime = Date.now();
            return quotaCache;
          }
        } catch (e2) {}
      }
      return quotaCache || [];
    })().finally(function () {
      quotaPending = null;
    });

    return quotaPending;
  }

  var sessionCache = new Map();

  // 获取指定会话的完整生成指标（TPS、TTFT、Token计数、缓存命中率）
  async function fetchSessionMetrics(conversationId, force) {
    if (!conversationId) return null;
    var entry = sessionCache.get(conversationId);
    if (!force && entry && (Date.now() - entry.time < 2000)) {
      return entry.data;
    }

    try {
      var raw = await callLanguageServer('GetCascadeTrajectory', { cascadeId: conversationId });
      var fresh = trajectoryMetrics(raw);
      sessionCache.set(conversationId, { time: Date.now(), data: fresh });
      return fresh;
    } catch (err) {
      if (entry) return entry.data;
      return null;
    }
  }

  // 挂载原版标准的 window.agPulseHost 接口
  window.agPulseHost = {
    getPreferences: async function () {
      return getStoredPreferences();
    },

    setPreferences: async function (input) {
      return saveStoredPreferences(input);
    },

    getMetrics: async function (input) {
      var cid = input && input.conversationId;
      var force = input && input.force;

      var groups = [];
      try {
        groups = await fetchQuotaMetrics(force);
      } catch (_) {}

      var speed = null;
      if (cid) {
        try {
          speed = await fetchSessionMetrics(cid, force);
        } catch (_) {}
      }

      var isDark = document.body ? (document.body.classList.contains('theme-dark') || !document.body.classList.contains('theme-light')) : false;

      return {
        connection: 'live',
        error: null,
        sessionError: null,
        serverTime: new Date().toISOString(),
        quotaUpdatedAt: quotaCacheTime ? new Date(quotaCacheTime).toISOString() : null,
        groups: groups,
        speed: speed,
        usage: null,
        theme: {
          mode: isDark ? 'dark' : 'light',
          light: { primary: '#0284c7', background: '#ffffff' }
        },
        source: 'Antigravity Android Local Core'
      };
    },

    report: function (stage, details) {
      // 诊断日志
      // console.log('[agPulse]', stage, details);
    },

    updatePlugin: async function () {
      return { upToDate: true };
    }
  };

  // 挂载移动端增强的 surface 探测器
  window.__agPulseSurface = {
    showEmpty: true,
    findComposer: function (previous) {
      var box = document.querySelector('[data-testid="agent-input-box"]');
      if (box) {
        var card = box.querySelector('#antigravity\\.agentSidePanelInputBox') || box.querySelector('.bg-card')?.parentElement || (box.children.length > 0 ? box.children[box.children.length - 1] : null);
        var editor = box.querySelector('[aria-label="Message input"]') || box.querySelector('[role="textbox"]') || box.querySelector('[contenteditable="true"]');
        var model = box.querySelector('[data-testid="model-selector-trigger"]');
        if (card && editor) {
          var branch = card.previousElementSibling;
          if (!branch || branch.id === 'ag-pulse-status-bar') {
            var anchor = box.querySelector('.ag-pulse-anchor');
            if (!anchor) {
              anchor = document.createElement('div');
              anchor.className = 'ag-pulse-anchor';
              anchor.style.cssText = 'height:0;margin:0;padding:0;overflow:hidden;';
              box.insertBefore(anchor, card);
            }
            branch = anchor;
          }
          return {
            editor: editor,
            model: model,
            row: box,
            branch: branch,
            box: box,
            distance: 1,
            kind: 'main'
          };
        }
      }
      return null;
    },
    conversationId: function (composer) {
      var owner = (composer?.box || composer?.row)?.closest('[data-cascade-id]');
      if (owner) {
        var id = owner.getAttribute('data-cascade-id');
        if (/^[0-9a-f-]{36}$/i.test(id)) return id;
      }
      var selected = document.querySelector('[data-cascade-id][data-selected="true"]');
      if (selected) {
        var sid = selected.getAttribute('data-cascade-id');
        if (/^[0-9a-f-]{36}$/i.test(sid)) return sid;
      }
      try {
        var m = window.location.pathname.match(/\/c\/([0-9a-f-]{36})/i);
        if (m) return m[1];
        var mh = window.location.hash.match(/\/c\/([0-9a-f-]{36})/i);
        if (mh) return mh[1];
        var q = new URLSearchParams(window.location.search);
        var qId = q.get('c') || q.get('cascadeId');
        if (qId && /^[0-9a-f-]{36}$/i.test(qId)) return qId;
      } catch (_) {}
      return null;
    }
  };

  console.log('[agDashboard] 1:1 原版 host-bridge 驱动就绪。');// end host bridge
