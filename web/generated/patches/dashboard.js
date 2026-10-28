(function(){
// 原版 context.mjs 移植
// The current request's host-reported capacity is the occupancy denominator.
// Provider specifications are separately sourced references, never overrides.
const count=value=>(typeof value==='number'||typeof value==='string'&&/^\d+$/.test(value))&&Number.isSafeInteger(Number(value))&&Number(value)>=0?Number(value):null;
const aliases=new Map([
 ['model_placeholder_m318','Gemini 3.8 Flash (High)'],
 ['model_placeholder_m319','Gemini 3.8 Flash (Medium)'],
 ['model_placeholder_m320','Gemini 3.8 Flash (Low)'],
 ['model_placeholder_m35','Claude Sonnet 4.6 (Thinking)'],
 ['model_placeholder_m26','Claude Opus 4.6 (Thinking)'],
 ['model_openai_gpt_oss_120b_medium','GPT-OSS 120B (Medium)'],
]);
// Placeholder aliases above were checked against the installed host's model
// catalog on 2026-10-14. Unknown placeholders stay unknown, not a family guess.
function identify(model){
 if(typeof model!=='string')return null;
 let name=model.replace(/[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]/g,'').trim().slice(0,256);
 if(!name)return null;name=aliases.get(name.toLowerCase())||name;
 const normalized=name.toLowerCase().replace(/(\d)[._-](\d)/g,'$1.$2').replace(/[\s()_]+/g,'-').replace(/-+$/,'');
 let match=normalized.match(/^gemini-3\.8-flash(?:-(n|high|medium|low))?$/);
 if(match)return {key:'gemini-3.8-flash',display:'Gemini 3.8 Flash'+(match[1]&&match[1]!=='n'?` (${match[1][0].toUpperCase()+match[1].slice(1)})`:'')};
 match=normalized.match(/^claude-(sonnet|opus)-(4\.6|5\.5)(?:-(thinking|high|medium|low))?(?:-\d{8})?$/);
 if(match)return {key:`claude-${match[1]}-${match[2]}`,display:`Claude ${match[1][0].toUpperCase()+match[1].slice(1)} ${match[2]}`+(match[3]?` (${match[3][0].toUpperCase()+match[3].slice(1)})`:'')};
 match=normalized.match(/^gpt-oss-120b(?:-(high|medium|low))?$/);
 if(match)return {key:'gpt-oss-120b',display:'GPT-OSS 120B'+(match[1]?` (${match[1][0].toUpperCase()+match[1].slice(1)})`:'')};
 return {key:null,display:name};
}
function formatModelName(model){return identify(model)?.display||null;}
function modelContextReference(model){
 const key=identify(model)?.key;
 if(key==='gemini-3.8-flash')return {tokens:1048576,label:'1,048,576',kind:'provider-input-limit',source:'https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash',checkedAt:'2026-10-14'};
 if(key==='gpt-oss-120b')return {tokens:131072,label:'131,072',kind:'provider-context-window',source:'https://developers.openai.com/api/docs/models/gpt-oss-120b',checkedAt:'2026-10-14'};
 if(/^claude-(sonnet|opus)-(4\.6|5\.5)$/.test(key||''))return {tokens:null,label:'1M',kind:'provider-context-window',source:`https://platform.claude.com/docs/en/models/${key.slice(7).replace('.', '-')}/overview`,checkedAt:'2026-10-14'};
 // Claude's inspected pages state "1M"; preserve that label rather than
 // inventing a precise 1,048,576-token limit or applying it to this host.
 return null;
}
function modelContextCapacity(model){return modelContextReference(model)?.tokens??null;}
function modelCompressionLimit(_model){
 // The inspected host schema has no compaction-threshold field. Neither the
 // provider's capacity nor the host's maxContextTokens proves a trigger value.
 return null;
}
function contextMetrics(metadata,{model=null,sampledAt=null}={}){
 if(!metadata||typeof metadata!=='object'||Array.isArray(metadata))return null;
 const usedTokens=count(metadata.estimatedTokensUsed),rawMax=count(metadata.maxContextTokens);
 if(usedTokens===null)return null;
 const maxTokens=rawMax>0?rawMax:null,reference=modelContextReference(model);
 return {
  usedTokens,maxTokens,remainingTokens:maxTokens===null?null:Math.max(0,maxTokens-usedTokens),
  usedFraction:maxTokens===null?null:usedTokens/maxTokens,
  remainingFraction:maxTokens===null?null:Math.max(0,1-usedTokens/maxTokens),
  capacitySource:maxTokens===null?null:'host-reported',
  providerMaxTokens:reference?.tokens??null,providerCapacityLabel:reference?.label??null,
  providerCapacitySource:reference?.source??null,providerCapacityKind:reference?.kind??null,
  providerCapacityCheckedAt:reference?.checkedAt??null,
  compressionLimit:null,compressionFraction:null,compressionSource:null,
  model:formatModelName(model),
  sampledAt:typeof sampledAt==='string'&&Number.isFinite(Date.parse(sampledAt))?new Date(sampledAt).toISOString():null,
  source:'Antigravity context window metadata',estimated:true,
 };
}
function safeContext(value){
 if(!value||typeof value!=='object'||Array.isArray(value))return null;
 // Recalculate all derived fields and provider references. Never trust ratios,
 // arbitrary source URLs, unsupported limits or additional saved properties.
 return contextMetrics({estimatedTokensUsed:value.usedTokens,maxContextTokens:value.maxTokens},{model:value.model,sampledAt:value.sampledAt});
}

// 原版 rate-quality.mjs 移植
// Summary-only timing checks: no chunk timestamps are exposed by this host.
// These flags mean unmeasurable/suspect, not proof of upstream buffering.
const RATE_VERSION = 2;
const RATE_REASONS = ['token-scope', 'duplicate-scope', 'retry-scope', 'short-tool-window', 'short-outlier', 'nonfinite-rate'];
const median = values => {
  const sorted = [...values].sort((a,b)=>a-b), mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid-1]+sorted[mid])/2;
};

function classifyRates(samples) {
  const profiles = new Map();
  for (const sample of samples) {
    if (sample.reasons.length || !(sample.duration >= 1) || !(sample.tps > 0)) continue;
    const key = sample.profile;
    if (!profiles.has(key)) profiles.set(key, []);
    profiles.get(key).push(sample.tps);
  }
  const limits = new Map();
  for (const [key, rates] of profiles) {
    if (rates.length < 5) continue;
    const center = median(rates), mad = median(rates.map(rate=>Math.abs(rate-center)));
    limits.set(key, Math.max(center*8, center+12*mad));
  }
  for (const sample of samples) {
    if (!Number.isFinite(sample.tps) && sample.duration > 0 && sample.responseTokens !== null) sample.reasons.push('nonfinite-rate');
    // A tiny tool-only stream after a much longer wait gives no evidence that
    // its measured interval covers generation of the tool arguments. Keep its
    // usage/TTFT but quarantine its rate. Ordinary short text stays eligible.
    if (sample.duration > 0 && sample.duration < 1 && sample.responseTokens > 0 && sample.toolOnly &&
        sample.ttft >= 2 && sample.ttft / sample.duration >= 20) sample.reasons.push('short-tool-window');
    const limit = limits.get(sample.profile);
    sample.outlier = limit !== undefined && sample.tps > limit;
    // Distribution alone never rejects a sustained, potentially real high rate.
    if (sample.outlier && sample.duration < 1 && !sample.reasons.length) sample.reasons.push('short-outlier');
    sample.status = sample.reasons.length ? 'unreliable' : sample.responseTokens === null || !(sample.duration > 0) ? 'missing' : 'ok';
  }
  return samples;
}

// 原版 metrics.mjs 移植
// Pure transforms. No credentials, prompts, or message text enter the public result.


function seconds(value) {
  if (typeof value === 'number') return Number.isFinite(value) && value >= 0 ? value : null;
  if (typeof value === 'string' && /^\d+(?:\.\d+)?s$/.test(value)) {
    const n = Number(value.slice(0, -1));
    return Number.isFinite(n) ? n : null;
  }
  if (value && typeof value === 'object') {
    if (value.seconds === undefined && value.nanos === undefined) return null;
    const whole = Number(value.seconds ?? 0), nanos = Number(value.nanos ?? 0);
    if (!Number.isSafeInteger(whole) || whole < 0 || !Number.isInteger(nanos) || nanos < 0 || nanos >= 1e9) return null;
    const n = whole + nanos / 1e9;
    return Number.isFinite(n) && n >= 0 ? n : null;
  }
  return null;
}

function tokenCount(value) {
  if (typeof value !== 'number' && !(typeof value === 'string' && /^\d+$/.test(value))) return null;
  const n = Number(value);
  return Number.isSafeInteger(n) && n >= 0 ? n : null;
}

function requestCacheMetrics(usage) {
  const input = tokenCount(usage.inputTokens);
  if ((usage.cacheReadTokens !== undefined && tokenCount(usage.cacheReadTokens) === null) ||
      (usage.cacheWriteTokens !== undefined && tokenCount(usage.cacheWriteTokens) === null)) return null;
  const read = tokenCount(usage.cacheReadTokens) ?? 0;
  const write = tokenCount(usage.cacheWriteTokens) ?? 0;
  const provider = String(usage.apiProvider || '');
  if (input === null) return null;
  // Antigravity ModelUsageStats normalizes inputTokens to uncached input,
  // including Gemini (verified against live records with cacheRead > input).
  // These are NOT upstream Gemini/OpenAI prompt_tokens. Add the separate
  // cache read/write counts exactly once for this local interface.
  const total = input + read + write;
  // A tool follow-up can explicitly report zero input. It is a valid neutral
  // sample, even though an all-zero denominator cannot produce a hit ratio.
  if (!Number.isSafeInteger(total) || total < 0 || read + write > total) return null;
  // A provider label is unnecessary for a validated zero denominator: it
  // contributes neither numerator nor denominator and never invents a ratio.
  if (total > 0 && !/GOOGLE_GEMINI|OPENAI|ANTHROPIC/.test(provider)) return null;
  return { inputTokens:total, cachedTokens:read, cacheWriteTokens:write, uncachedTokens:total-read-write };
}

function unionSeconds(intervals) {
  const sorted = intervals.filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b) && b >= a).sort((a, b) => a[0] - b[0]);
  let total = 0, start = null, end = null;
  for (const [a, b] of sorted) {
    if (start === null) { start = a; end = b; }
    else if (a <= end) end = Math.max(end, b);
    else { total += end - start; start = a; end = b; }
  }
  if (start !== null) total += end - start;
  return total / 1000;
}

function trajectoryMetrics(response) {
  const trajectory = response.trajectory || {};
  const generators = trajectory.generatorMetadata || [];
  const samples = [], ids = new Map();
  const steps = trajectory.steps || [];
  const counts = { input: 0, output: 0, responseOutput: 0, thinkingOutput: 0, cacheRead: 0, cacheWrite: 0 };
  let modelSeconds = 0, ttftSeconds = 0, ttftSamples = 0, missingTiming = 0;
  const cache = { inputTokens:0, cachedTokens:0, cacheWriteTokens:0, uncachedTokens:0, outputTokens:0, measuredRequests:0, missingRequests:0 };
  // Token availability is independent of cache-ratio availability. In particular,
  // a historical request may retain output usage but lack normalized input data.
  const tokens = { inputTokens:0, cachedTokens:0, cacheWriteTokens:0, uncachedTokens:0, outputTokens:0,
    measuredRequests:0, inputRequests:0, outputRequests:0, missingInputRequests:0, missingOutputRequests:0,
    uncachedRequests:0, cachedRequests:0, cacheWriteRequests:0 };
  for (const [index, generator] of generators.entries()) {
    const chat = generator.chatModel;
    if (!chat?.usage) continue;
    const usage = chat.usage;
    // IDE executionId identifies a planner run/turn, not an individual model
    // request: tool follow-ups share it while having distinct responseIds.
    // Never collapse those follow-ups, even when no request ID was returned.
    const id = usage.responseId ? `response:${usage.apiProvider||''}:${usage.responseId}`
      : usage.messageId ? `message:${usage.messageId}` : `index:${index}`;
    const signature = JSON.stringify([usage.outputTokens,usage.responseOutputTokens,usage.thinkingOutputTokens,
      seconds(chat.streamingDuration),seconds(chat.timeToFirstToken),chat.responseModel,chat.model,usage.model]);
    if (ids.has(id)) {
      const previous = ids.get(id);
      if (previous.signature !== signature && !previous.sample.reasons.includes('duplicate-scope')) previous.sample.reasons.push('duplicate-scope');
      continue;
    }
    const cached = requestCacheMetrics(usage);
    if(cached) {
      for(const key of ['inputTokens','cachedTokens','cacheWriteTokens','uncachedTokens'])cache[key]+=cached[key];
      cache.outputTokens+=tokenCount(usage.outputTokens)??0;
      cache.measuredRequests++;
    } else cache.missingRequests++;
    const output = tokenCount(usage.outputTokens);
    // These fields come from the local normalized ModelUsageStats contract,
    // not upstream prompt_tokens. Account for each readable component even
    // when another component (or the cache-ratio provider) is unavailable.
    const input = tokenCount(usage.inputTokens);
    const read = usage.cacheReadTokens === undefined && input !== null ? 0 : tokenCount(usage.cacheReadTokens);
    const write = usage.cacheWriteTokens === undefined && input !== null ? 0 : tokenCount(usage.cacheWriteTokens);
    const parts = [['uncachedTokens','uncachedRequests',input],['cachedTokens','cachedRequests',read],['cacheWriteTokens','cacheWriteRequests',write]];
    for (const [field,coverage,value] of parts) if (value !== null) {
      tokens[field] = tokens[field] === null ? null : tokenCount(tokens[field]+value);
      tokens[coverage]++;
    }
    if (input !== null && read !== null && write !== null && tokenCount(input+read+write) !== null) tokens.inputRequests++;
    else tokens.missingInputRequests++;
    if (output !== null) { tokens.outputTokens = tokens.outputTokens === null ? null : tokenCount(tokens.outputTokens+output); tokens.outputRequests++; }
    else tokens.missingOutputRequests++;
    if (parts.some(([, ,value])=>value!==null) || output !== null) tokens.measuredRequests++;
    const visible = tokenCount(usage.responseOutputTokens);
    const thinking = tokenCount(usage.thinkingOutputTokens);
    // Gemini may finish thinking before the first visible streaming token. Pair the
    // response token count with streamingDuration; do not charge thinking to that span.
    const responseTokens = visible ?? (output !== null && thinking !== null ? Math.max(0, output - thinking) : output);
    const duration = seconds(chat.streamingDuration);
    const ttft = seconds(chat.timeToFirstToken);
    counts.input += tokenCount(usage.inputTokens) ?? 0;
    counts.output += output ?? 0;
    counts.responseOutput += responseTokens ?? 0;
    counts.thinkingOutput += thinking ?? 0;
    counts.cacheRead += tokenCount(usage.cacheReadTokens) ?? 0;
    counts.cacheWrite += tokenCount(usage.cacheWriteTokens) ?? 0;
    if (ttft !== null) { ttftSeconds += ttft; ttftSamples++; }
    modelSeconds += (ttft ?? 0) + (duration ?? 0);
    const reasons = [];
    if (['outputTokens','responseOutputTokens','thinkingOutputTokens'].some(key=>usage[key] !== undefined && tokenCount(usage[key]) === null) ||
        output !== null && (visible !== null && visible > output || thinking !== null && thinking > output ||
          visible !== null && thinking !== null && visible + thinking > output)) reasons.push('token-scope');
    // One retryInfos entry is the ordinary attempt record, not evidence of a retry.
    // Multiple differing usage records lack attempt-specific timing in this API.
    const attempts = (Array.isArray(chat.retryInfos) ? chat.retryInfos : []).filter(info=>info?.usage);
    if (attempts.length > 1 && attempts.some(info=>['outputTokens','responseOutputTokens','thinkingOutputTokens'].some(key=>
        tokenCount(info.usage[key]) !== tokenCount(usage[key])))) reasons.push('retry-scope');
    const planners = (generator.stepIndices || []).map(i=>Number.isInteger(i) && i >= 0 ? steps[i] : null)
      .filter(step=>/PLANNER_RESPONSE/.test(String(step?.type || '')));
    const toolOnly = planners.length > 0 && planners.every(step=>step.plannerResponse?.toolCalls?.length > 0 &&
      !String(step.plannerResponse?.response || '').trim());
    const basis = visible !== null || thinking !== null ? 'response' : 'all-output';
    const sample = { responseTokens, duration, ttft, reasons, toolOnly,
      tps: responseTokens !== null && duration > 0 ? responseTokens / duration : null,
      model: chat.modelDisplayName || chat.responseModel || String(chat.model || usage.model || ''), basis,
      profile: JSON.stringify([usage.apiProvider || '',chat.responseModel || usage.model || chat.model || chat.modelDisplayName || '',basis]) };
    samples.push(sample);
    ids.set(id,{signature,sample});
  }
  classifyRates(samples);
  const accepted = samples.filter(sample=>sample.status === 'ok');
  missingTiming = samples.filter(sample=>sample.status === 'missing' && sample.responseTokens > 0).length;
  const excludedTiming = samples.filter(sample=>sample.status === 'unreliable').length;
  const rateWarnings = samples.filter(sample=>sample.status === 'ok' && (sample.duration < 1 || sample.outlier)).length;
  const timingReasons = Object.fromEntries(RATE_REASONS.map(reason=>[reason,samples.filter(sample=>sample.reasons.includes(reason)).length]));
  const streamingSeconds = accepted.reduce((sum, s) => sum + s.duration, 0);
  const sampledTokens = accepted.reduce((sum, s) => sum + s.responseTokens, 0);
  const basisSamples = accepted.length ? accepted : samples;
  const tools = steps.filter(s => /SEARCH_WEB|BROWSE|RUN_COMMAND|COMMAND|READ|WRITE|EDIT|CODE_ACTION|TOOL|MCP|LIST|GREP|VIEW|FIND|TERMINAL/i.test(String(s.type || '')) || s.metadata?.toolCall);
  const toolSeconds = unionSeconds(tools.map(s => [Date.parse(s.metadata.startedAt || s.metadata.createdAt), Date.parse(s.metadata.completedAt)]));
  const latest = samples.at(-1) || null;
  const lastChat = [...generators].reverse().find(g => g.chatModel)?.chatModel;
  const inputParts=[tokens.uncachedTokens,tokens.cachedTokens,tokens.cacheWriteTokens];
  tokens.inputTokens = tokenCount(inputParts.reduce((sum,value)=>sum+(value??0),0));
  const totalTokens=tokenCount((tokens.inputTokens??0)+(tokens.outputTokens??0));
  return {
    source: 'Antigravity request metadata', status: response.status || null,
    conversationId: trajectory.cascadeId || null,
    steps: Number(response.numTotalSteps ?? steps.length), rounds: steps.filter(s => /USER_INPUT/.test(String(s.type))).length,
    requests: ids.size, measuredRequests: accepted.length, missingTiming, excludedTiming, rateWarnings, timingReasons, rateVersion: RATE_VERSION, counts,
    tokens:{...tokens,totalTokens,
      complete:tokens.missingInputRequests===0&&tokens.missingOutputRequests===0&&inputParts.every(value=>value!==null)&&tokens.outputTokens!==null&&totalTokens!==null},
    cache:{...cache,totalTokens:cache.inputTokens+cache.outputTokens,hitRate:cache.inputTokens>0?cache.cachedTokens/cache.inputTokens:null,complete:cache.missingRequests===0},
    tps: streamingSeconds > 0 ? sampledTokens / streamingSeconds : null, latestTps: latest?.status === 'ok' ? latest.tps : null,
    latestRateStatus: latest?.status ?? 'missing',
    rateBasis: basisSamples.length && basisSamples.every(s => s.basis === 'response') ? 'response' : 'all-output',
    streamingSeconds, modelSeconds, toolSeconds, ttftSeconds: ttftSamples ? ttftSeconds / ttftSamples : null,
    latestShortSample: latest?.status === 'ok' && latest.duration < 1, model: latest?.model || null,
    context: contextMetrics(lastChat?.chatStartMetadata?.contextWindowMetadata, {
      model:lastChat?.modelDisplayName || lastChat?.responseModel || String(lastChat?.model || ''),
      sampledAt:lastChat?.chatStartMetadata?.createdAt,
    }),
    complete: Number(response.numTotalGeneratorMetadata ?? generators.length) === generators.length,
  };
}

function quotaMetrics(response, now = Date.now()) {
  const root = response.response || response;
  const groups = root.groups?.length ? root.groups : root.buckets?.length ? [{ displayName: '账户额度', buckets: root.buckets }] : [];
  return groups.map((group, index) => ({
    id: group.buckets?.[0]?.bucketId?.replace(/-(5h|weekly)$/, '') || `group-${index}`,
    name: group.displayName || `额度组 ${index + 1}`, description: group.description || '',
    windows: Object.fromEntries(['5h', 'weekly'].map(window => {
      const bucket = (group.buckets || []).find(b => b.window === window || b.bucketId?.endsWith(`-${window}`));
      if (!bucket) return [window, { available: false, reason: '账户未返回此额度窗口' }];
      const fraction = Number(bucket.remainingFraction);
      const remaining = bucket.remainingFraction !== undefined && Number.isFinite(fraction) && fraction >= 0 && fraction <= 1 ? fraction : null;
      const date = Date.parse(bucket.resetTime);
      return [window, { available: true, id: bucket.bucketId, remaining, amount: tokenCount(bucket.remainingAmount),
        resetAt: Number.isFinite(date) ? new Date(date).toISOString() : null,
        expired: Number.isFinite(date) && date <= now, disabled: bucket.disabled === true, description: bucket.description || '' }];
    })),
  }));
}

// 原版 theme.cjs 移植
window.__agPulseThemeFactory = (function createAgPulseTheme() {
  const palettes = {
    dark: { scheme:'dark', page:'#121315', background:'#1c1d1f', card:'#2a2c2f', 'card-end':'#303235', foreground:'#e1e3e7', chip:'#aaaeb6', muted:'#adb2ba', subtle:'#a3aab5', label:'#b8bdc5', hover:'#292b2e', 'hover-text':'#d9dce2', accent:'#85a8ff', emphasis:'#dbe5ff', border:'#41454d', separator:'#ffffff15', track:'#ffffff15', control:'#383b3f', 'control-text':'#c2c7d1', menu:'#303338', selected:'#444950', ring:'#9fadc7', 'ring-track':'#565c67', dot:'#777c84', success:'#8bb19b', warning:'#d7b079', danger:'#e99b9b', shadow:'#0005' },
    light: { scheme:'light', page:'#f5f6f8', background:'#ffffff', card:'#ffffff', 'card-end':'#f5f7fa', foreground:'#202631', chip:'#485261', muted:'#596575', subtle:'#626d7c', label:'#515c6b', hover:'#e9edf3', 'hover-text':'#172333', accent:'#315fc4', emphasis:'#284e9b', border:'#ccd3df', separator:'#18253b20', track:'#dce2ec', control:'#e8edf4', 'control-text':'#354255', menu:'#ffffff', selected:'#e4ebf6', ring:'#4667a0', 'ring-track':'#c5cedd', dot:'#707b8a', success:'#347451', warning:'#8b601b', danger:'#b13c3c', shadow:'#14234026' },
  };
  const declarations = theme => Object.entries(palettes[theme]).map(([key,value])=>`--pulse-${key}:${value}`).join(';');
  function css(selector) {
    return `${selector}{${declarations('dark')}}${selector}[data-pulse-theme="light"]{${declarations('light')}}@media(prefers-color-scheme:light){${selector}:not([data-pulse-theme]){${declarations('light')}}}`;
  }
  // Shadow selectors need the attribute inside :host(), unlike ordinary DOM.
  function shadowCss() {
    return `:host{${declarations('dark')}}:host([data-pulse-theme="light"]){${declarations('light')}}`;
  }
  function normalizeHostTheme(value) {
    const result={};
    if(!value||typeof value!=='object'||Array.isArray(value))return result;
    if(['dark','light','system'].includes(value.mode))result.mode=value.mode;
    for(const mode of ['dark','light']){
      for(const key of ['primary','background','foregroundOverride']){
        const color=value[mode]?.[key];
        if(typeof color!=='string'||!/^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(color))continue;
        (result[mode]||={})[key]=(color.length===4?'#'+Array.from(color.slice(1),v=>v+v).join(''):color).toLowerCase();
      }
    }
    return result;
  }
  const luminance=rgb=>rgb.map(value=>{value/=255;return value<=.04045?value/12.92:((value+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
  const contrast=(a,b)=>(Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
  const mix=(a,b,amount)=>a.map((value,i)=>Math.round(value+(b[i]-value)*amount));
  const colorCss=color=>'rgb('+color.join(' ')+')';
  function attach(target, { embedded = false } = {}) {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const canvas = document.createElement('canvas'); canvas.width=canvas.height=1;
    const context = canvas.getContext('2d', { willReadFrequently:true });
    let stopped=false,hostTheme={};
    function rgb(color) {
      if (!color || !context || !CSS.supports('color',color)) return null;
      context.clearRect(0,0,1,1); context.fillStyle='transparent';context.fillStyle=color; context.fillRect(0,0,1,1);
      const [r,g,b,a]=context.getImageData(0,0,1,1).data;
      if (a<250) return null; // Transparent surfaces do not define a theme.
      return [r,g,b];
    }
    function fromColor(color) {
      const values=rgb(color);return values ? .2126*values[0]+.7152*values[1]+.0722*values[2]>=145?'light':'dark' : null;
    }
    function explicit(element) {
      if (!element) return null;
      for (const key of ['data-theme','data-color-mode','data-theme-mode','data-vscode-theme-kind']) {
        const value=element.getAttribute(key)?.toLowerCase();
        if (/^(light|light-theme|vs|vscode-light|hc-light)$/.test(value)) return 'light';
        if (/^(dark|dark-theme|vs-dark|vscode-dark|hc-black|hc-dark)$/.test(value)) return 'dark';
      }
      const classes=element.classList;
      const light=['light','light-theme','theme-light','vscode-light','vs'].some(value=>classes.contains(value));
      const dark=['dark','dark-theme','theme-dark','vscode-dark','vs-dark','hc-black'].some(value=>classes.contains(value));
      return light===dark ? null : light ? 'light' : 'dark';
    }
    function resolve() {
      const root=document.documentElement;
      // App settings override the OS, including when the app uses a fixed theme.
      const declared=explicit(document.body)||explicit(root);
      if (declared) return declared;
      // The sidecar SDK pushes --background on theme-change messages.
      const sdk=fromColor(getComputedStyle(root).getPropertyValue('--background').trim());
      if (sdk) return sdk;
      if (embedded) {
        for (let element=target.parentElement;element;element=element.parentElement) {
          const theme=explicit(element)||fromColor(getComputedStyle(element).backgroundColor);
          if (theme) return theme;
        }
        const scheme=getComputedStyle(root).colorScheme;
        if (scheme==='light'||scheme==='dark') return scheme;
      }
      if(hostTheme.mode==='light'||hostTheme.mode==='dark')return hostTheme.mode;
      return media.matches ? 'dark' : 'light';
    }
    function hostColor(tokens) {
      // The renderer's active primary wins over saved seeds: a user may have
      // switched back to a preset while retaining custom-theme settings.
      const elements=embedded?[target.parentElement,document.body,document.documentElement]:[document.documentElement,document.body];
      for(const element of elements.filter(Boolean)){
        const style=getComputedStyle(element);
        for(const token of tokens){
          const value=style.getPropertyValue(token).trim();
          if(!value)continue;
          const color=rgb(value)||rgb(`hsl(${value})`);
          if(color)return color;
        }
      }
      return null;
    }
    function readableColor(color,surfaces) {
      const readable=values=>surfaces.every(surface=>contrast(values,surface)>=4.5);
      if(readable(color))return colorCss(color);
      // Keep the selected hue while ensuring small accent text stays legible.
      const ends=[[255,255,255],[0,0,0]];
      const score=values=>Math.min(...surfaces.map(surface=>contrast(values,surface)));
      const end=score(ends[0])>=score(ends[1])?ends[0]:ends[1];
      for(let step=1;step<=100;step++){
        const mixed=mix(color,end,step/100);
        if(readable(mixed))return colorCss(mixed);
      }
      return colorCss(end);
    }
    function surfaceColors(theme) {
      let background=hostColor(['--background','--color-background'])||rgb(hostTheme[theme]?.background);
      if(!background&&embedded){
        for(let element=target.parentElement;element;element=element.parentElement){
          background=rgb(getComputedStyle(element).backgroundColor);if(background)break;
        }
      }
      if(!background)return {};
      // Use actual host card surfaces (including color-mix/OKLCH) where available.
      // If only a seed exists, derive a subtle raised surface in the same hue.
      const dark=luminance(background)<.35,end=dark?[255,255,255]:[0,0,0];
      let card=hostColor(['--popover','--card','--color-card'])||mix(background,end,dark?.05:.015);
      // Wildly incompatible host tokens must not make shared text unreadable.
      const commonContrast=bg=>Math.max(...[[255,255,255],[0,0,0]].map(fg=>Math.min(contrast(fg,background),contrast(fg,bg))));
      if(commonContrast(card)<4.5)card=mix(background,end,dark?.05:.015);
      const hover=mix(card,end,.06),control=mix(card,end,.08),selected=mix(card,end,.12);
      const surfaces=[background,card,hover,control,selected];
      const foreground=hostColor(['--foreground','--color-foreground'])||rgb(hostTheme[theme]?.foregroundOverride)||rgb(palettes[dark?'dark':'light'].foreground);
      const text=rgb(readableColor(foreground,surfaces));
      const values={page:background,background,card,'card-end':card,menu:card,hover,control,selected,
        foreground:text,chip:mix(card,text,.8),muted:mix(card,text,.75),subtle:mix(card,text,.7),label:mix(card,text,.8),
        'hover-text':text,'control-text':mix(card,text,.85),border:mix(card,text,.24),separator:mix(card,text,.14),track:mix(card,text,.14),
        'ring-track':mix(card,text,.24),dot:mix(card,text,.6)};
      for(const key of ['chip','muted','subtle','label','control-text'])values[key]=rgb(readableColor(values[key],surfaces));
      return Object.fromEntries(Object.entries(values).map(([key,value])=>[key,colorCss(value)]));
    }
    function update() {
      if (stopped) return;
      const theme=resolve();
      if (target.dataset.pulseTheme!==theme) target.dataset.pulseTheme=theme;
      const values=surfaceColors(theme);
      const surfaces=[values.card||palettes[theme].card,values.background||palettes[theme].background,values.control||palettes[theme].control].map(rgb);
      const primary=hostColor(['--primary','--color-primary'])||rgb(hostTheme[theme]?.primary);
      if(primary){values.accent=colorCss(primary);values.ring=colorCss(primary);}
      if(primary||values.card)values.emphasis=readableColor(primary||rgb(palettes[theme].emphasis),surfaces);
      // Severity text must also remain readable on custom surfaces.
      if(values.card)for(const key of ['success','warning','danger'])values[key]=readableColor(rgb(palettes[theme][key]),surfaces);
      for(const key of Object.keys(palettes[theme])){
        const property='--pulse-'+key,value=values[key];
        if(value){if(target.style.getPropertyValue(property)!==value)target.style.setProperty(property,value);}
        else if(target.style.getPropertyValue(property))target.style.removeProperty(property);
      }
      return theme;
    }
    const observer=new MutationObserver(update);
    const attributes=['class','style','data-theme','data-color-mode','data-theme-mode','data-vscode-theme-kind'];
    const elements=new Set([document.documentElement,document.body]);
    if (embedded) for(let element=target.parentElement;element;element=element.parentElement) elements.add(element);
    for(const element of elements) if(element) observer.observe(element,{attributes:true,attributeFilter:attributes});
    if(document.head) observer.observe(document.head,{childList:true,subtree:true,attributes:true,attributeFilter:['href','media','disabled']});
    media.addEventListener('change',update);
    // Catch stylesheet replacement and reparented composers without observing chat text.
    const timer=setInterval(update,1500);
    update();
    return { update, setHostTheme(value) { hostTheme=normalizeHostTheme(value);return update(); }, dispose() { stopped=true;observer.disconnect();media.removeEventListener('change',update);clearInterval(timer); } };
  }
  return { css, shadowCss, attach, normalizeHostTheme };
});

// 原版 i18n.cjs 移植
window.__agPulseI18nFactory = (function createDashboardI18n(initialLanguage) {
  const dictionary={
    en:{
      tokenPartial:'Known tokens only (≥): {input} requests lack input usage; {output} lack output usage. Output is counted independently of cache availability.',
      tokenLegacy:'Saved token usage is a lower bound (≥); request-level coverage cannot be verified.',unknownCoverage:'unknown',
      cacheZeroInput:'Reported total input is 0; the cache hit rate has no denominator.',
      savedCache:'Cache ratio uses saved statistics ({time}).',savedSpeed:'Speed uses saved statistics ({time}).',
      panelSpeed:'Speed',panelCache:'Cache',panelContext:'Context',panelDetails:'Metric details',panelUsed:'used',panelSharedQuota:'Shared quota',
      newConversationStats:'New conversation: send a message or open an existing conversation to view its statistics. Account quota is shown separately below.',
      subagentStats:'Current subagent statistics',accountQuota:'Account quota, shared across agents.',
      taskOwn:'Current agent',taskSubagents:'Subagents ({n})',taskLoading:'Summing subagents…',taskPartial:'Some subagents unavailable',
      transcriptTitle:'Recorded text estimate',transcriptUser:'User text',transcriptAssistant:'Replies + thinking',transcriptTool:'Tool output',transcriptSystem:'System text',transcriptMarkers:'Compaction markers',transcriptImages:'Image-generation steps',transcriptPartial:'partial',transcriptLoading:'Loading…',transcriptUnavailable:'Unavailable',transcriptSaved:'saved',transcriptBasis:'Estimated logged text, not active context or billed usage. Hidden prompts, media and tool-call arguments are excluded.',
      contextHostLimit:'Active window (host)',contextProviderCapacity:'Provider capacity reference',contextCompressionLimit:'Compaction threshold',contextLimitUnknown:'Unknown',contextReferenceBasis:'Provider specification; not this session\'s available capacity.',
      context:'Context window',contextShort:'Ctx',contextUsed:'{used}% used ({remaining}% left)',contextTokens:'{used} / {max} tok',contextUnknown:'Context capacity unavailable',contextUnavailable:'Context statistics are unavailable for this request.',contextBasis:'Host estimate at the latest request start; not cumulative tokens or a live streaming counter.',contextModel:'Sampled model',contextLimit:'Window capacity',contextUsage:'Used tokens (estimate)',contextSaved:'Showing saved context statistics ({time}).',contextExceeded:'The host estimate exceeds the reported capacity.',
      savedStats:'Showing saved conversation statistics ({time}).',saveFailed:'Statistics could not be saved locally.',
      strip:'Antigrative Dashboard statistics',session:'Session statistics',cache:'Cache hit',cacheTitle:'Token usage',five:'Five-hour quota',week:'Weekly quota',weekShort:'Wk',
      modelTime:'Model time',toolTime:'Tool time',ttft:'Average TTFT',sessionTps:'Session TPS',latest:'Last request',tokens:'Response / thinking',remaining:'remaining',
      resetIn:'Resets in',resetTime:'Reset time (UTC+8)',group:'Quota group',selectGroup:'Select quota group',refresh:'Refresh quota',refreshStats:'Refresh statistics',refreshing:'Refreshing…',
      waiting:'Waiting for refresh',connecting:'Connecting to Antigravity…',waitingApp:'Waiting for Antigravity',waitingModel:'Waiting for a model request',waitingRequest:'No requests yet',
      hover:'Hover over the strip for details',autoConnect:'Open the app to connect automatically',loadingQuota:'Loading quota…',unavailableQuota:'Quota unavailable',
      live:'Connected to Antigrative Dashboard',stale:'Showing last available quota',offline:'Antigrative Dashboard is offline',
      responseBasis:'Calculation: response tokens ÷ streaming time; session TPS is time-weighted.',allBasis:'Calculation: output tokens ÷ streaming time; response and thinking are not separated.',
      missingTime:'{n} requests lack timing and are excluded from TPS.',shortSample:'Last request is under 1s; its rate may vary substantially.',running:'Generating; showing completed requests.',
      timingUnreliable:'Timing uncertain',ratePending:'Awaiting recalculation',excludedTime:'{n} requests with uncertain timing are excluded from TPS.',rateWarning:'Another {n} short or unusually fast samples remain included in TPS; their rates may fluctuate.',rateWarningOnly:'{n} short or unusually fast samples remain included in TPS; their rates may fluctuate.',rateReasons:'Reason: {reasons}.',rateReasonCount:'{reason}: {n} requests',rateUsageRetained:'Token and cache usage is still retained in full.',legacyRate:'Saved TPS uses the old calculation. Reopen this conversation while connected to recalculate.',
      reasonToken:'Token scope mismatch',reasonDuplicate:'Conflicting request records',reasonRetry:'Retry/token timing scope uncertain',reasonTool:'Short tool-only timing window',reasonOutlier:'Short sample far above same-model baseline',reasonNonfinite:'Invalid calculated rate',
      sample:'{rounds} turns · {steps} steps · {requests} samples',sampleCount:'{n} samples',rounds:'{rounds} turns {steps} steps ·',
      noQuota:'This account did not return this quota window.',disabledQuota:'This quota window is disabled.',noFraction:'The account did not return a remaining fraction.',
      sharedQuota:'Models in this group share quota.',quotaSource:'Balances and reset times come from the account API.',updated:'Updated {time}',health:'Quota updated {time} · actual request metrics',firstUpdate:'Waiting for the first update',
      cacheRate:'Cache hit',cacheRead:'Cache read',cacheInput:'Total input',cacheMiss:'Uncached input',cacheWrite:'Cache write',cacheOutput:'Output',
      cacheBasis:'Cached input ÷ total input, weighted across requests. Cache writes are not hits.',cacheMissing:'{n} requests have unavailable cache statistics.',cacheUnavailable:'Cache statistics are unavailable for this conversation.',
      cacheCoverage:'{measured} of {total} requests',language:'Language',switchLanguage:'Switch to Chinese',languageSaveFailed:'Language preference could not be saved. Please retry.',reconnecting:'Waiting to reconnect',panelUnavailable:'The statistics panel cannot connect right now.',invalidData:'Incompatible statistics data',
    },
    'zh-CN':{
      tokenPartial:'仅统计已知 Token（≥）：{input} 次请求缺少输入用量，{output} 次缺少输出用量。输出独立于缓存统计。',
      tokenLegacy:'已保存 Token 用量为下界（≥）；无法确认逐请求统计覆盖情况。',unknownCoverage:'未知',
      cacheZeroInput:'报告的总输入为 0，缓存命中率无可计算的分母。',
      savedCache:'缓存率使用已保存统计（{time}）。',savedSpeed:'速度使用已保存统计（{time}）。',
      panelSpeed:'速度',panelCache:'缓存',panelContext:'上下文',panelDetails:'统计详情',panelUsed:'已用',panelSharedQuota:'共享额度',
      newConversationStats:'当前为新对话：发送消息或打开已有对话后显示该会话统计。账号额度在下方单独展示。',
      subagentStats:'当前子代理统计',accountQuota:'账号共享额度，所有代理共用。',
      taskOwn:'当前代理',taskSubagents:'子代理（{n}）',taskLoading:'正在汇总子代理…',taskPartial:'部分子代理暂不可读取',
      transcriptTitle:'已记录文本估算',transcriptUser:'用户文本',transcriptAssistant:'回复与思考',transcriptTool:'工具输出',transcriptSystem:'系统文本',transcriptMarkers:'压缩标记记录',transcriptImages:'图像生成步骤',transcriptPartial:'不完整',transcriptLoading:'读取中…',transcriptUnavailable:'不可用',transcriptSaved:'已保存',transcriptBasis:'日志文本估算，非当前上下文或计费用量。不含隐藏提示、媒体和工具调用参数。',
      contextHostLimit:'当前窗口容量（宿主）',contextProviderCapacity:'供应商容量参考',contextCompressionLimit:'压缩触发阈值',contextLimitUnknown:'未知',contextReferenceBasis:'供应商规格参考，不代表当前会话可用容量。',
      context:'上下文窗口',contextShort:'上下文',contextUsed:'{used}% 已用（剩余 {remaining}%）',contextTokens:'{used} / {max} tok',contextUnknown:'上下文容量不可用',contextUnavailable:'此请求暂无可用上下文统计。',contextBasis:'宿主在最近请求开始时的估计值，非累计 Token，也非流式实时计数。',contextModel:'采样模型',contextLimit:'窗口容量',contextUsage:'已用 Token（估计）',contextSaved:'显示已保存的上下文统计（{time}）。',contextExceeded:'宿主估计值超过返回的窗口容量。',
      savedStats:'显示已保存的会话统计（{time}）。',saveFailed:'统计暂时无法保存到本地。',
      strip:'Antigrative Dashboard 会话与额度状态条',session:'会话统计',cache:'缓存命中',cacheTitle:'Token 用量',five:'5h 额度',week:'周额度',weekShort:'周',
      modelTime:'模型调用用时',toolTime:'工具调用用时',ttft:'首 token 平均（TTFT）',sessionTps:'会话输出速率（TPS）',latest:'最近一次请求',tokens:'正文 / 思考输出',remaining:'剩余',
      resetIn:'重置倒计时',resetTime:'重置时间（北京时间）',group:'额度组',selectGroup:'选择额度组',refresh:'刷新额度',refreshStats:'刷新统计',refreshing:'正在刷新…',
      waiting:'等待刷新',connecting:'连接 Antigravity…',waitingApp:'等待 Antigravity',waitingModel:'等待模型生成',waitingRequest:'尚无请求',hover:'悬停状态条，查看详细统计',autoConnect:'打开应用后自动连接',loadingQuota:'读取额度…',unavailableQuota:'额度暂不可用',
      live:'已连接 Antigrative Dashboard',stale:'显示上次成功读取的额度',offline:'Antigrative Dashboard 暂未连接',
      responseBasis:'统计方式：正文 Token ÷ 流式时长；会话 TPS 按总时长加权。',allBasis:'统计方式：输出 Token ÷ 流式时长；此模型未拆分正文与思考。',
      missingTime:'{n} 次请求缺少时长，未计入 TPS。',shortSample:'最近请求不足 1 秒，单次速率波动较大。',running:'生成中，显示已完成请求统计。',
      timingUnreliable:'计时异常',ratePending:'等待重算',excludedTime:'已排除 {n} 次异常计时，不计入 TPS。',rateWarning:'另有 {n} 次短时或高速度采样可能波动，仍计入 TPS。',rateWarningOnly:'{n} 次短时或高速度采样可能波动，仍计入 TPS。',rateReasons:'原因：{reasons}。',rateReasonCount:'{reason}：{n} 次',rateUsageRetained:'Token 和缓存用量仍完整保留。',legacyRate:'已保存的 TPS 使用旧算法；连接后打开此对话即可重新计算。',
      reasonToken:'Token 统计范围不一致',reasonDuplicate:'同一请求的记录冲突',reasonRetry:'重试的 Token 与计时范围不明确',reasonTool:'工具输出的计时窗口过短',reasonOutlier:'短时速率显著高于同模型基线',reasonNonfinite:'计算速率无效',
      sample:'{rounds}轮 {steps}步 · {requests} 次采样',sampleCount:'{n} 次采样',rounds:'{rounds}轮 {steps}步 ·',
      noQuota:'账户未返回此额度窗口。',disabledQuota:'此额度窗口已停用。',noFraction:'账户未返回剩余比例。',sharedQuota:'同组模型共享额度。',quotaSource:'余额与重置时间来自账户接口。',updated:'{time} 更新',health:'额度更新于 {time} · 真实请求统计',firstUpdate:'等待首次更新',
      cacheRate:'缓存命中',cacheRead:'缓存读取',cacheInput:'总输入',cacheMiss:'未缓存输入',cacheWrite:'缓存写入',cacheOutput:'输出',cacheBasis:'缓存读取 token ÷ 总输入 token，按请求 token 总量加权；缓存写入不算命中。',cacheMissing:'{n} 次请求缺少缓存统计。',cacheUnavailable:'此会话暂无可用缓存统计。',cacheCoverage:'{measured} / {total} 次请求',
      language:'语言',switchLanguage:'Switch to English',languageSaveFailed:'语言设置暂时无法保存，请重试。',reconnecting:'等待控件重新连接',panelUnavailable:'统计面板暂时无法连接',invalidData:'统计数据格式不兼容',
    },
    'zh-TW':{
      tokenPartial:'僅統計已記錄的 Token（≥）：{input} 次請求缺少輸入用量，{output} 次缺少輸出用量。輸出計算獨立於快取統計。',
      tokenLegacy:'已儲存的 Token 用量為下限（≥）；無法確認個別請求的統計涵蓋情況。',unknownCoverage:'未知',
      cacheZeroInput:'回報的總輸入為 0，快取命中率無有效的分母可供計算。',
      savedCache:'快取率使用已儲存的統計資料（{time}）。',savedSpeed:'生成速率使用已儲存的統計資料（{time}）。',
      panelSpeed:'速率',panelCache:'快取',panelContext:'上下文',panelDetails:'統計詳細資料',panelUsed:'已用',panelSharedQuota:'共用配額',
      newConversationStats:'目前為新對話：傳送訊息或開啟既有對話後將顯示統計資料。帳號配額於下方單獨顯示。',
      subagentStats:'目前子代理 (Subagent) 統計',accountQuota:'帳號共用配額，供所有代理共用。',
      taskOwn:'目前代理',taskSubagents:'子代理（{n}）',taskLoading:'正在彙總子代理…',taskPartial:'部分子代理暫時無法讀取',
      transcriptTitle:'已記錄文字預估',transcriptUser:'使用者文字',transcriptAssistant:'回覆與思考過程',transcriptTool:'工具輸出',transcriptSystem:'系統文字',transcriptMarkers:'壓縮標記記錄',transcriptImages:'圖片生成步驟',transcriptPartial:'部分記錄',transcriptLoading:'載入中…',transcriptUnavailable:'無法提供',transcriptSaved:'已儲存',transcriptBasis:'依記錄文字推算之預估值，非作用中上下文或計費用量。不含隱藏提示詞、媒體檔案與工具呼叫引數。',
      contextHostLimit:'目前視窗容量（宿主環境）',contextProviderCapacity:'供應商規格容量參考',contextCompressionLimit:'觸發壓縮門檻',contextLimitUnknown:'未知',contextReferenceBasis:'模型供應商規格參考值，不代表目前對話的可用容量。',
      context:'上下文視窗',contextShort:'上下文',contextUsed:'{used}% 已使用（剩餘 {remaining}%）',contextTokens:'{used} / {max} tok',contextUnknown:'目前無法取得上下文容量',contextUnavailable:'此請求目前無法取得上下文統計資料。',contextBasis:'宿主環境於最近一次請求發起時的預估值，非累計 Token，亦非串流即時計數。',contextModel:'取樣模型',contextLimit:'視窗容量',contextUsage:'已用 Token（預估）',contextSaved:'顯示已儲存的上下文統計資料（{time}）。',contextExceeded:'宿主預估值已超過回傳的視窗容量。',
      savedStats:'顯示已儲存的對話統計資料（{time}）。',saveFailed:'統計資料暫時無法儲存至本機。',
      strip:'Antigrative Dashboard 對話與配額狀態列',session:'工作階段統計',cache:'快取命中',cacheTitle:'Token 用量',five:'5 小時配額',week:'每週配額',weekShort:'週',
      modelTime:'模型呼叫耗時',toolTime:'工具呼叫耗時',ttft:'首字回應平均時間 (TTFT)',sessionTps:'連線階段輸出速率 (TPS)',latest:'最近一次請求',tokens:'回覆內文 / 思考輸出',remaining:'剩餘',
      resetIn:'重設倒數',resetTime:'重設時間 (UTC+8)',group:'配額群組',selectGroup:'選取配額群組',refresh:'重新整理配額',refreshStats:'重新整理統計',refreshing:'正在重新整理…',
      waiting:'等待重新整理',connecting:'連線至 Antigravity…',waitingApp:'等待 Antigravity',waitingModel:'等待模型生成',waitingRequest:'尚無請求',hover:'將游標移至狀態列可檢視詳細統計',autoConnect:'開啟應用程式後將自動連線',loadingQuota:'讀取配額中…',unavailableQuota:'配額暫時無法取得',
      live:'已連線至 Antigrative Dashboard',stale:'顯示前次成功讀取的配額',offline:'Antigrative Dashboard 尚未連線',
      responseBasis:'統計方式：回覆 Token ÷ 串流耗時；連線階段 TPS 依總時長加權計算。',allBasis:'統計方式：輸出 Token ÷ 串流耗時；此模型未區分回覆與思考過程。',
      missingTime:'{n} 次請求缺少耗時記錄，未計入 TPS。',shortSample:'最近一次請求耗時未滿 1 秒，單次速率波動可能較大。',running:'生成中，目前顯示已完成請求之統計。',
      timingUnreliable:'計時異常',ratePending:'等待重新計算',excludedTime:'已排除 {n} 次計時異常的請求，不計入 TPS。',rateWarning:'另有 {n} 次短時間或極高速取樣可能存在波動，仍已計入 TPS。',rateWarningOnly:'{n} 次短時間或極高速取樣可能存在波動，仍已計入 TPS。',rateReasons:'原因：{reasons}。',rateReasonCount:'{reason}：{n} 次',rateUsageRetained:'Token 與快取用量仍完整保留。',legacyRate:'已儲存的 TPS 使用舊版演算法；連線後重新開啟此對話即可重新計算。',
      reasonToken:'Token 統計範圍不一致',reasonDuplicate:'同一請求存在衝突記錄',reasonRetry:'重試的 Token 與計時範圍不明確',reasonTool:'純工具輸出的計時區間過短',reasonOutlier:'短時間速率顯著高於同模型基準線',reasonNonfinite:'計算速率無效',
      sample:'{rounds} 輪 {steps} 步 · {requests} 次取樣',sampleCount:'{n} 次取樣',rounds:'{rounds} 輪 {steps} 步 ·',
      noQuota:'此帳號未回傳該配額區間。',disabledQuota:'此配額區間已停用。',noFraction:'帳號未回傳剩餘比例。',sharedQuota:'同群組之模型共用配額。',quotaSource:'餘額與重設時間來自帳號 API。',updated:'{time} 更新',health:'配額更新於 {time} · 真實請求指標',firstUpdate:'等待初次更新',
      cacheRate:'快取命中率',cacheRead:'快取讀取',cacheInput:'總輸入',cacheMiss:'未快取輸入',cacheWrite:'快取寫入',cacheOutput:'輸出',cacheBasis:'快取讀取 Token ÷ 總輸入 Token，依各請求之 Token 總量加權計算；快取寫入不列入命中。',cacheMissing:'{n} 次請求缺少快取統計資料。',cacheUnavailable:'此對話目前無法取得快取統計資料。',cacheCoverage:'{measured} / {total} 次請求',
      language:'語言',switchLanguage:'Switch to English',languageSaveFailed:'語言設定暫時無法儲存，請再試一次。',reconnecting:'等待控制項重新連線',panelUnavailable:'統計面板暫時無法連線',invalidData:'統計資料格式不相容',
    },
  };
  let language=initialLanguage==='zh-CN'||initialLanguage==='zh-TW'?initialLanguage:'en';
  let lastZh=initialLanguage==='zh-TW'?'zh-TW':'zh-CN';
  const t=(key,args={})=>(dictionary[language]?.[key]||dictionary.en[key]||key).replace(/\{(\w+)\}/g,(_,name)=>String(args[name]??''));
  function countdown(at,now=Date.now(),compact=false){
    const end=Date.parse(at);if(!Number.isFinite(end))return '—';if(end<=now)return t('waiting');
    const left=Math.ceil((end-now)/1000),days=Math.floor(left/86400),hours=Math.floor(left%86400/3600),mins=Math.floor(left%3600/60),secs=left%60,pad=n=>String(n).padStart(2,'0');
    return `${days?`${days}${language==='en'?'d':'天'} `:''}${pad(hours)}:${pad(mins)}${compact&&days?'':`:${pad(secs)}`}`;
  }
  function elapsed(value){
    if(typeof value!=='number'||!Number.isFinite(value))return '—';if(value<60)return `${value.toFixed(2)}${language==='en'?'s':' 秒'}`;
    const whole=Math.round(value),h=Math.floor(whole/3600),m=Math.floor(whole%3600/60),s=whole%60;
    if(language==='en')return `${h?`${h}h `:''}${m}m ${s}s`;
    if(language==='zh-TW')return `${h?`${h} 小時 `:''}${m} 分 ${s} 秒`;
    return `${h?`${h}小时`:''}${m}分${s}秒`;
  }
  function resetDate(value){
    const date=new Date(value);return Number.isFinite(date.getTime())?new Intl.DateTimeFormat(language==='en'?'en-GB':(language==='zh-TW'?'zh-TW':'zh-CN'),{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Shanghai'}).format(date):'—';
  }
  function errorMessage(value){
    if(!value)return '';
    const key=Object.keys(dictionary.en).find(key=>dictionary.en[key]===value);
    if(key)return t(key);
    if(language==='zh-CN')return value;
    if(language==='zh-TW'){
      const twErrors={
        '请先打开 Antigravity':'請先開啟 Antigravity','当前采集适配器支持 Windows':'目前收集配接器僅支援 Windows',
        '检测到多个 Antigravity 实例，请保留一个':'偵測到多個 Antigravity 執行個體，請保留一個',
        '未找到 Antigravity 桌面后台':'找不到 Antigravity 桌面背景程式',
        '当前版本未提供可用的本地检测凭据':'目前版本未提供可用的本機檢測憑證',
        '等待 Antigravity 本地接口启动':'等待 Antigravity 本機 API 啟動',
        '未找到 Antigravity 语言服务日志，请检查日志路径':'找不到 Antigravity 語言伺服器記錄，請檢查記錄路徑',
        '会话暂时没有可用统计':'此對話暫無可用統計資料',
        '完整会话统计分页暂不可用':'完整對話統計分頁暫時無法取得',
        '会话统计数据超过内存预算':'對話統計資料超出記憶體預算',
        '会话统计数据超过采集上限':'對話統計資料超出收集上限',
        '会话统计字段超过采集上限':'對話統計欄位超出收集上限',
        '会话统计分页读取超时':'對話統計分頁讀取逾時',
        '会话统计分页数量无效':'對話統計分頁數量無效',
        '会话统计分页格式无效':'對話統計分頁格式無效',
        '会话仍在更新，请等待下一次刷新':'對話仍在更新中，請等待下一次重新整理',
        '接口响应超过采集上限':'API 回應超出收集上限',
        'Antigravity 接口返回了无法解析的数据':'Antigravity API 回傳了無法解析的資料',
        'Antigravity 本地接口超时':'Antigravity 本機 API 連線逾時',
        '会话标识无效':'對話識別碼無效',
        '等待 Antigrative Dashboard 后台启动':'等待 Antigrative Dashboard 背景程式啟動',
        '等待 Antigrative Dashboard 重新连接':'等待 Antigrative Dashboard 重新連線',
        '等待 AG Pulse 后台启动':'等待 AG Pulse 背景程式啟動',
        '等待 AG Pulse 重新连接':'等待 AG Pulse 重新連線',
      };
      if(twErrors[value])return twErrors[value];
      const match=String(value).match(/^Antigravity 接口 (\w+) 返回 (\d+)$/);
      if(match)return `Antigravity API ${match[1]} 回傳 HTTP ${match[2]}`;
      return t('panelUnavailable');
    }
    const errors={
      '请先打开 Antigravity':'Open Antigravity to connect.', '当前采集适配器支持 Windows':'This collector requires Windows.',
      '检测到多个 Antigravity 实例，请保留一个':'Multiple Antigravity instances detected. Keep one open.',
      '未找到 Antigravity 桌面后台':'Antigravity desktop backend was not found.',
      '当前版本未提供可用的本地检测凭据':'Local metrics credentials are unavailable in this version.',
      '等待 Antigravity 本地接口启动':'Waiting for the local Antigravity API.',
      '未找到 Antigravity 语言服务日志，请检查日志路径':'Antigravity language-server log was not found. Check the log path.',
      '会话暂时没有可用统计':'No statistics are available for this conversation yet.',
      '完整会话统计分页暂不可用':'Complete conversation statistics are temporarily unavailable.',
      '会话统计数据超过内存预算':'Conversation statistics exceed the memory budget.',
      '会话统计数据超过采集上限':'Retained conversation statistics exceed the collection budget.',
      '会话统计字段超过采集上限':'A statistics field exceeds the collection budget.',
      '会话统计分页读取超时':'Conversation statistics pagination timed out.',
      '会话统计分页数量无效':'Invalid conversation statistics page count.',
      '会话统计分页格式无效':'Invalid conversation statistics page format.',
      '会话仍在更新，请等待下一次刷新':'The conversation is updating; waiting for the next refresh.',
      '接口响应超过采集上限':'The API response exceeds the collection budget.',
      'Antigravity 接口返回了无法解析的数据':'Antigravity returned an invalid response.',
      'Antigravity 本地接口超时':'The local Antigravity API timed out.',
      '会话标识无效':'Invalid conversation identifier.',
      '等待 Antigrative Dashboard 后台启动':'Waiting for the dashboard background process.',
      '等待 Antigrative Dashboard 重新连接':'Waiting for the dashboard to reconnect.',
      '等待 AG Pulse 后台启动':'Waiting for the dashboard background process.',
      '等待 AG Pulse 重新连接':'Waiting for the dashboard to reconnect.',
    };
    if(errors[value])return errors[value];
    const match=String(value).match(/^Antigravity 接口 (\w+) 返回 (\d+)$/);
    return match?`Antigravity ${match[1]} returned HTTP ${match[2]}.`:'Statistics are temporarily unavailable.';
  }
  function connectPreferences({read,write,cache=()=>{},changed=()=>{}}) {
    let epoch=0,writes=0,revision=-1,disposed=false,error=false,queue=Promise.resolve();
    const valid=value=>value==='en'||value==='zh-CN'||value==='zh-TW';
    const notify=()=>{if(!disposed)changed();};
    const remember=()=>{try{cache(language);}catch{}};
    const check=value=>{if(!value||value.error||!Object.hasOwn(value,'language')||value.language!==null&&!valid(value.language))throw new Error('Invalid preference response');return value;};
    function sync(value) {
      if(disposed||writes)return;
      try {
        check(value);const next=Number.isSafeInteger(value.revision)?value.revision:0;
        if(next<revision)return;
        if(error&&epoch>0&&value.language!==language)return; // retain an unsaved choice and its warning
        if(value.language===null&&epoch===0&&valid(initialLanguage)){void choose(initialLanguage);return;}
        revision=next;error=false;
        if(valid(value.language)&&language!==value.language){language=value.language;if(value.language!=='en')lastZh=value.language;remember();}
        notify();
      } catch {error=true;notify();}
    }
    function choose(value) {
      if(disposed||!valid(value))return Promise.resolve();
      const choice=++epoch;language=value;if(value!=='en')lastZh=value;writes++;error=false;remember();notify();
      const pending=queue.then(async()=>{
        try {
          const saved=check(await write({language:value}));
          if(saved.language!==value)throw new Error('Preference acknowledgement differs');
          revision=Math.max(revision,Number.isSafeInteger(saved.revision)?saved.revision:0);
          if(choice===epoch)error=false;
        } catch {if(choice===epoch)error=true;}
        finally {writes--;notify();}
      });
      queue=pending;return pending;
    }
    const ready=(async()=>{
      const started=epoch;
      try {
        const saved=check(await read());
        if(disposed||epoch!==started)return;
        if(saved.language===null&&valid(initialLanguage))await choose(initialLanguage); // migrate an existing browser choice once
        else sync(saved);
      }catch{if(!disposed&&epoch===started){error=true;notify();}}
    })();
    return {ready,sync,choose,toggle:()=>choose(language==='en'?(lastZh||'zh-TW'):'en'),get error(){return error;},get pending(){return writes>0;},dispose(){disposed=true;}};
  }
  // The factory is serialized into both the sandboxed panel and IDE webviews.
  // Build the selector without HTML sinks, imports or host-specific APIs.
  function mountLanguagePicker({button,parent=button.parentNode,choose,label=button}) {
    const doc=button.ownerDocument,menu=doc.createElement('div');
    menu.setAttribute('popover','manual');menu.setAttribute('role','menu');
    menu.dataset.languageMenu='';
    menu.style.cssText='position:fixed;inset:auto;margin:0;padding:5px;min-width:140px;box-sizing:border-box;border:1px solid var(--pulse-border);border-radius:9px;background:var(--pulse-card,var(--pulse-background));color:var(--pulse-foreground);box-shadow:0 8px 24px var(--pulse-shadow);font:12px system-ui;z-index:2147483647';
    const options=[['en','English'],['zh-CN','简体中文'],['zh-TW','繁體中文']].map(([code,name])=>{
      const item=doc.createElement('button');item.type='button';item.textContent=name;item.lang=code;item.dataset.language=code;item.setAttribute('role','menuitemradio');
      item.style.cssText='display:block;width:100%;min-height:32px;padding:7px 12px;border:0;border-radius:5px;text-align:left;font:inherit;color:inherit;background:transparent;cursor:pointer';
      item.addEventListener('click',()=>{close();void choose(code);});
      item.addEventListener('focus',()=>item.style.background='var(--pulse-hover)');item.addEventListener('blur',()=>update());
      menu.append(item);return item;
    });
    parent.append(menu);button.setAttribute('aria-haspopup','menu');button.setAttribute('aria-expanded','false');
    const isOpen=()=>menu.matches(':popover-open');
    function close(restore=true){if(isOpen())menu.hidePopover();button.setAttribute('aria-expanded','false');if(restore)button.focus({preventScroll:true});}
    function position(){if(!isOpen())return;const r=button.getBoundingClientRect(),m=menu.getBoundingClientRect(),win=doc.defaultView;menu.style.left=Math.max(6,Math.min(r.right-m.width,win.innerWidth-m.width-6))+'px';menu.style.top=(r.bottom+m.height+6<win.innerHeight?r.bottom+5:Math.max(6,r.top-m.height-5))+'px';}
    function update(){label.textContent=language==='en'?'EN':language==='zh-TW'?'繁':'中';menu.setAttribute('aria-label',t('language'));button.setAttribute('aria-label',t('language'));button.title=t('language');for(const item of options){const selected=item.dataset.language===language;item.setAttribute('aria-checked',String(selected));item.style.background=selected?'var(--pulse-selected,var(--pulse-hover))':'transparent';}position();}
    function open(){update();menu.showPopover();button.setAttribute('aria-expanded','true');position();options.find(item=>item.dataset.language===language).focus({preventScroll:true});}
    function toggle(){if(isOpen())close();else open();}
    function keys(event){if(!isOpen())return;const path=event.composedPath(),index=options.findIndex(item=>path.includes(item));
      if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();close();return;}
      if(event.key==='Tab'){close(false);return;}
      if(index<0)return;let next;if(event.key==='ArrowDown')next=(index+1)%3;else if(event.key==='ArrowUp')next=(index+2)%3;else if(event.key==='Home')next=0;else if(event.key==='End')next=2;else return;
      event.preventDefault();event.stopImmediatePropagation();options[next].focus({preventScroll:true});
    }
    function outside(event){const path=event.composedPath();if(isOpen()&&!path.includes(menu)&&!path.includes(button))close(false);}
    button.addEventListener('click',toggle);doc.addEventListener('keydown',keys,true);doc.addEventListener('pointerdown',outside,true);doc.defaultView.addEventListener('resize',position);
    update();return {update,close,isOpen,dispose(){close(false);button.removeEventListener('click',toggle);doc.removeEventListener('keydown',keys,true);doc.removeEventListener('pointerdown',outside,true);doc.defaultView.removeEventListener('resize',position);menu.remove();}};
  }
  function rateNote(speed) {
    if (!speed) return t('waitingRequest');
    if (speed.latestRateStatus === 'legacy') return t('ratePending');
    return t(speed.rateBasis==='all-output'?'allBasis':'responseBasis');
  }
  return {mountLanguagePicker,t,rateNote,countdown,elapsed,resetDate,errorMessage,connectPreferences,get language(){return language;},setLanguage(value){language=value==='zh-CN'||value==='zh-TW'?value:'en';if(language!=='en')lastZh=language;},toggle(){language=language==='en'?(lastZh||'zh-TW'):'en';return language;}};
});

// 原版 usage-ui.cjs 移植
window.__agPulseUsageFactory = (function createUsageDashboard({root,language,setMarkup,hostLabel='Antigravity',guideDismissed=false,onDismissGuide,onLanguage,onRefresh}) {
  const dialog=document.createElement('dialog');dialog.id='usage-dashboard';dialog.setAttribute('popover','manual');dialog.setAttribute('aria-modal','true');dialog.setAttribute('aria-label',language.language==='zh-TW'?'用量統計':language.language==='zh-CN'?'用量统计':'Token usage');
  dialog.style.cssText='width:min(1040px,calc(100vw - 40px));max-width:none;height:min(820px,calc(100dvh - 64px));max-height:none;box-sizing:border-box;overflow:hidden;visibility:visible;pointer-events:auto;padding:0;border:1px solid var(--pulse-border);border-radius:18px;background:var(--pulse-background);color:var(--pulse-foreground);box-shadow:0 24px 100px #0006';
  const shell=document.createElement('div'),view=shell.attachShadow({mode:'open'});shell.style.height='100%';dialog.append(shell);root.append(dialog);
  const backdrop=document.createElement('style');backdrop.textContent='#usage-dashboard{position:fixed;inset:0;margin:auto}#usage-dashboard::backdrop{background:#0006;backdrop-filter:blur(3px);pointer-events:auto}';root.append(backdrop);
  const css=document.createElement('style');css.textContent=`
    :host{display:block;color:var(--pulse-foreground);font:13px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;font-variant-numeric:tabular-nums}
    *{box-sizing:border-box}button,select{font:inherit;color:inherit}button{cursor:pointer}button,select{border:1px solid var(--pulse-border);background:transparent;border-radius:7px}button{transition:background 140ms ease,transform 120ms cubic-bezier(.23,1,.32,1)}button:active{transform:scale(.97)}button:focus-visible,select:focus-visible{outline:2px solid var(--pulse-accent);outline-offset:3px}button[disabled]{opacity:.35;cursor:default}
    .page{padding:28px 32px 24px;max-height:90dvh;overflow:auto;background:var(--pulse-background)}.top{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.eyebrow{font-size:10px;color:var(--pulse-muted);letter-spacing:1.7px;margin-bottom:7px}h1{font-size:24px;letter-spacing:-.7px;line-height:1.2;margin:0 0 8px;font-weight:600}.sub{font-size:12px;color:var(--pulse-muted)}.actions{display:flex;gap:8px;align-items:center}.actions button{display:grid;place-items:center;flex:0 0 32px;width:32px;height:32px;padding:0;line-height:1;border-radius:8px;color:var(--pulse-muted)}.actions button:hover{background:var(--pulse-hover);color:var(--pulse-foreground)}.actions svg{display:block;width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}.locale-label{display:block;min-width:16px;height:16px;line-height:16px;text-align:center;font-size:11px}.live-dot{display:inline-block;width:5px;height:5px;background:var(--pulse-success);border-radius:50%;margin-right:6px}
    .tabs{display:flex;gap:22px;border-bottom:1px solid var(--pulse-separator);margin:25px 0 22px}.tabs button{border:0;border-radius:0;background:transparent;color:var(--pulse-muted);padding:0 2px 11px;position:relative}.tabs button[aria-selected=true]{color:var(--pulse-foreground);font-weight:600}.tabs button[aria-selected=true]:after{content:'';position:absolute;height:2px;background:var(--pulse-accent);bottom:-1px;left:0;right:0}
    .totals{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--pulse-border);border-radius:12px;padding:17px 0;margin-bottom:28px}.metric{padding:0 20px}.metric+.metric{border-left:1px solid var(--pulse-separator)}.metric label{color:var(--pulse-muted);font-size:11px}.value{font-size:27px;letter-spacing:-.9px;margin:5px 0 0;font-weight:550}.unit{font-size:11px;color:var(--pulse-muted);margin-left:5px;font-weight:400;letter-spacing:0}
    section[hidden]{display:none}.section-head{display:flex;align-items:center;justify-content:space-between;gap:15px;margin:0 0 18px}h2{font-size:14px;font-weight:600;letter-spacing:-.2px;margin:0}.muted{font-size:11px;color:var(--pulse-muted)}.seg{display:flex;padding:3px;background:var(--pulse-hover);border-radius:8px;gap:2px}.seg button{border:0;padding:4px 12px;border-radius:5px;font-size:11px;color:var(--pulse-muted)}.seg button[aria-pressed=true]{background:var(--pulse-control);color:var(--pulse-foreground);box-shadow:0 1px 3px #0001}select{padding:4px 8px;font-size:11px;background:var(--pulse-background)}
    .heat-wrap{overflow-x:auto;padding:3px 3px 7px}.calendar{min-width:680px}.months{display:grid;margin-left:31px;font-size:10px;color:var(--pulse-muted);margin-bottom:7px}.heat-row{display:flex;gap:9px}.weekdays{display:grid;grid-template-rows:repeat(7,1fr);width:22px;flex:none;font-size:9px;color:var(--pulse-muted)}.heat{display:grid;grid-auto-flow:column;grid-template-rows:repeat(7,1fr);gap:3px;width:100%}.heat button{border:0;border-radius:3px;padding:0;min-width:0;aspect-ratio:1;background:var(--pulse-hover);outline-offset:1px}.heat button[data-level="1"],.swatch[data-level="1"]{background:color-mix(in srgb,var(--pulse-accent) 22%,var(--pulse-hover))}.heat button[data-level="2"],.swatch[data-level="2"]{background:color-mix(in srgb,var(--pulse-accent) 45%,var(--pulse-hover))}.heat button[data-level="3"],.swatch[data-level="3"]{background:color-mix(in srgb,var(--pulse-accent) 68%,var(--pulse-hover))}.heat button[data-level="4"],.swatch[data-level="4"]{background:var(--pulse-accent)}.heat button.future{opacity:.25;cursor:default}.heat.week{grid-template-columns:repeat(26,minmax(0,1fr))!important;grid-template-rows:repeat(2,1fr);grid-auto-flow:row}.week button{max-height:28px;aspect-ratio:1}.heat-footer{display:flex;justify-content:space-between;align-items:center;gap:16px;margin:10px 0 27px;font-size:10px;color:var(--pulse-muted)}.scale{display:flex;align-items:center;gap:4px}.swatch{width:11px;height:11px;border-radius:3px;background:var(--pulse-hover)}.selected{padding:16px 18px;border:1px solid var(--pulse-border);border-radius:10px;display:flex;justify-content:space-between;gap:16px;align-items:center}.selected button{border:0;color:var(--pulse-accent);font-size:12px;padding:5px}.selected .title{font-weight:500;margin-bottom:3px}.selected strong{font-weight:550}
    .chart-controls{display:flex;gap:10px;align-items:center}.range{display:flex;align-items:center;gap:10px}.range button{height:26px;width:26px;border:0}.range strong{font-size:12px;font-weight:500;min-width:106px;text-align:center}.legend{display:flex;flex-wrap:wrap;gap:7px;margin:0 0 18px}.legend button{display:flex;align-items:center;gap:7px;padding:5px 9px;border-radius:6px;font-size:11px;border-color:transparent;background:var(--pulse-hover)}.legend button[aria-pressed=false]{opacity:.35}.dot{width:8px;height:8px;border-radius:2px;display:inline-block;flex:none;background:var(--model-color)}
    .chart-wrap{overflow-x:auto;border-bottom:1px solid var(--pulse-separator);padding-bottom:17px;margin-bottom:18px}.chart{height:246px;display:flex;gap:10px;min-width:650px}.axis{width:42px;flex:none;position:relative;font-size:9px;color:var(--pulse-muted)}.axis span{position:absolute;right:0;transform:translateY(50%)}.plot{position:relative;flex:1;display:flex;align-items:stretch;gap:6px;padding:0 1px}.grid-line{position:absolute;left:0;right:0;border-top:1px solid var(--pulse-separator);pointer-events:none}.bar-column{position:relative;flex:1;min-width:0;display:flex;align-items:flex-end;border:0;border-radius:4px;background:transparent;padding:0;margin-bottom:19px}.bar-column:hover{background:var(--pulse-hover)}.stack{display:flex;flex-direction:column-reverse;width:100%;gap:1px;pointer-events:none;border-radius:3px 3px 0 0;overflow:hidden}.bar-segment{width:100%;background:var(--model-color);min-height:1px}.x-label{position:absolute;top:calc(100% + 5px);left:50%;transform:translateX(-50%);font-size:9px;color:var(--pulse-muted);white-space:nowrap}.empty-bar{height:2px;width:100%;background:var(--pulse-track);border-radius:2px}.chart-empty{position:absolute;left:0;right:0;top:40%;text-align:center;color:var(--pulse-muted);font-size:12px;pointer-events:none}.table-wrap{overflow:auto}.table{width:100%;border-collapse:collapse;text-align:right;font-size:11px;white-space:nowrap}.table th{font-weight:400;color:var(--pulse-muted);padding:8px 12px;border-bottom:1px solid var(--pulse-separator)}.table td{padding:12px;border-bottom:1px solid var(--pulse-separator)}.table th:first-child,.table td:first-child{text-align:left;padding-left:0}.table td:first-child span{margin-right:7px}.table tr:last-child td{border-bottom:0}.footer{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:20px;font-size:10px;color:var(--pulse-muted)}.alert{color:var(--pulse-warning);margin-top:12px;font-size:11px}.tip{position:fixed;z-index:20;max-width:280px;padding:12px 14px;border:1px solid var(--pulse-border);border-radius:9px;background:var(--pulse-menu);box-shadow:0 8px 30px var(--pulse-shadow);color:var(--pulse-foreground);font-size:11px;pointer-events:none}.tip[hidden]{display:none}.tip .tip-title{font-size:10px;color:var(--pulse-muted);margin-bottom:5px}.tip strong{font-size:16px;font-weight:550}.tip-model{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-top:5px}.tip-model .dot{margin-right:6px}
    @media(max-width:650px){.page{padding:20px 18px}.totals{grid-template-columns:repeat(2,minmax(0,1fr));gap:15px 0}.metric:nth-child(3){border-left:0}.value{font-size:23px}.section-head{align-items:flex-start;flex-wrap:wrap}.chart-controls{width:100%;justify-content:space-between}.footer{align-items:flex-start;flex-direction:column;gap:5px}.selected{align-items:flex-start}.chart{gap:8px}}@media(prefers-reduced-motion:reduce){button{transition:none}button:active{transform:none}}
  `;view.append(css);
  css.textContent+=' .months span{white-space:nowrap}.chart-wrap{padding-top:9px}';
  css.textContent+=`
    :host{height:100%}.page{height:100%;max-height:none;display:flex;flex-direction:column;scrollbar-gutter:stable}.page>*{flex:none}.footer{margin-top:auto;padding-top:20px}
    .year-picker{position:relative;flex:none}.year-trigger{display:flex;align-items:center;justify-content:space-between;gap:14px;min-width:76px;height:30px;padding:0 10px;background:var(--pulse-control);color:var(--pulse-foreground);font-size:11px;border-radius:8px}.year-trigger:hover,.year-trigger[aria-expanded=true]{background:var(--pulse-hover)}.year-chevron{width:12px;height:12px;fill:none;stroke:var(--pulse-muted);stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;transition:transform 160ms cubic-bezier(.23,1,.32,1)}.year-trigger[aria-expanded=true] .year-chevron{transform:rotate(180deg)}
    .year-menu{position:fixed;inset:auto;margin:0;padding:5px;width:112px;max-height:232px;overflow-y:auto;border:1px solid var(--pulse-border);border-radius:10px;background:var(--pulse-menu);color:var(--pulse-foreground);box-shadow:0 8px 26px var(--pulse-shadow);transform-origin:top right;opacity:1;transform:scale(1);transition:opacity 140ms ease,transform 160ms cubic-bezier(.23,1,.32,1)}.year-menu::backdrop{background:transparent;pointer-events:none}.year-option{width:100%;border:0;border-radius:6px;padding:7px 9px;display:flex;align-items:center;justify-content:space-between;gap:18px;font-size:12px;text-align:left;background:transparent;color:var(--pulse-foreground);font-variant-numeric:tabular-nums}.year-option:hover,.year-option:focus-visible{background:var(--pulse-hover)}.year-option[aria-selected=true]{background:color-mix(in srgb,var(--pulse-accent) 12%,var(--pulse-menu))}.year-check{color:var(--pulse-accent);width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round;opacity:0}.year-option[aria-selected=true] .year-check{opacity:1}
    @starting-style{.year-menu:popover-open{opacity:0;transform:scale(.97)}}@media(prefers-reduced-motion:reduce){.year-menu,.year-chevron{transition:none}}
  `;
  css.textContent+=`
    .bar-column:hover{background:transparent}.bar-column:active{transform:none}.stack{width:62%;max-width:30px;margin-inline:auto;gap:0;border-radius:4px 4px 0 0;overflow:hidden}.bar-segment{display:block;flex:none;min-height:0;border-radius:0;pointer-events:auto;background:var(--model-color);transition:opacity 140ms ease}.plot[data-highlight] .bar-segment:not([data-highlight=true]){opacity:.24}.empty-bar{height:1px;opacity:.35}.grid-line{border-top-style:solid;opacity:.45}.grid-line:first-child{opacity:.85}.legend{gap:4px 18px;margin-bottom:22px}.legend button{background:transparent;padding:3px 0;border:0;border-radius:3px;color:var(--pulse-muted);gap:7px}.legend button:hover,.legend button[aria-pressed=true]{color:var(--pulse-foreground)}.legend button[aria-pressed=false]{opacity:.4;text-decoration:line-through}.legend .dot{width:7px;height:7px;border-radius:50%}.chart{gap:16px}.plot{gap:5px}.axis,.x-label{font-size:10px}.chart-summary{font-size:11px;color:var(--pulse-muted);margin-top:5px}.chart-summary strong{color:var(--pulse-foreground);font-weight:500}.chart-wrap{padding-top:6px}.table .dot{border-radius:50%}
    .tip-model{padding:3px 0}.tip-model.dimmed{opacity:.5}.tip-model.active{font-weight:600}.model-share{font-size:10px;color:var(--pulse-muted);margin-left:9px}.usage-waiting{display:grid;place-items:center;min-height:260px;color:var(--pulse-muted);font-size:12px}.usage-waiting[hidden]{display:none}
  `;
  const page=document.createElement('div');page.className='page';
  setMarkup(page,`<header class="top"><div><div class="eyebrow">ANTIGRATIVE DASHBOARD</div><h1 id="title"></h1><div class="sub"><span class="live-dot"></span><span id="subtitle"></span></div></div><div class="actions"><button id="locale" type="button" aria-label="Language"><span id="locale-label" class="locale-label">中</span></button><button id="refresh" type="button" aria-label="Refresh"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M13 7a5 5 0 1 0-1.3 4.4M13 3v4H9"/></svg></button><button id="close" type="button" aria-label="Close"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 4 8 8M12 4l-8 8"/></svg></button></div></header><nav class="tabs" role="tablist"><button id="overview-tab" role="tab" aria-controls="overview"></button><button id="details-tab" role="tab" aria-controls="details"></button></nav><div class="totals" id="totals"></div><section id="usage-waiting" class="usage-waiting" role="status" hidden></section><section id="overview" role="tabpanel"><div class="section-head"><div><h2 id="activity-title"></h2><div class="muted" id="heat-sub"></div></div><div class="chart-controls"><div class="seg" id="heat-controls"><button data-heat="day"></button><button data-heat="week"></button></div><div class="year-picker"><button id="year" type="button" class="year-trigger" aria-label="Year" aria-haspopup="listbox" aria-controls="year-menu" aria-expanded="false"><span id="year-label"></span><svg class="year-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg></button><div id="year-menu" class="year-menu" role="listbox" aria-label="Year" popover="manual"></div></div></div></div><div class="heat-wrap"><div class="calendar"><div class="months" id="months"></div><div class="heat-row"><div class="weekdays" id="weekdays"></div><div class="heat" id="heat"></div></div></div></div><div class="heat-footer"><span id="heat-summary"></span><div class="scale"><span id="less"></span><i class="swatch"></i><i class="swatch" data-level="1"></i><i class="swatch" data-level="2"></i><i class="swatch" data-level="3"></i><i class="swatch" data-level="4"></i><span id="more"></span></div></div><div class="selected"><div><div class="title" id="selection-title"></div><span class="muted" id="selection-value"></span></div><button id="selection-details"></button></div></section><section id="details" role="tabpanel" hidden><div class="section-head"><h2 id="detail-title"></h2><div class="chart-controls"><div class="range"><button id="previous" aria-label="Previous">‹</button><strong id="range-label"></strong><button id="next" aria-label="Next">›</button></div><div class="seg" id="period-controls"><button data-period="day"></button><button data-period="week"></button><button data-period="month"></button></div></div></div><div class="legend" id="legend"></div><div class="chart-wrap"><div class="chart"><div class="axis" id="axis"></div><div class="plot" id="plot"></div></div></div><div class="table-wrap"><table class="table"><thead><tr id="table-head"></tr></thead><tbody id="table-body"></tbody></table></div></section><div class="alert" id="alert" hidden></div><footer class="footer"><span id="coverage"></span><span id="timezone"></span></footer><div class="tip" id="tip" role="status" hidden></div>`);view.append(page);
  const intro=document.createElement('section');intro.id='usage-intro';intro.className='usage-intro';intro.hidden=true;intro.setAttribute('aria-labelledby','usage-intro-title');
  setMarkup(intro,'<div class="intro-heading"><span class="intro-mark" aria-hidden="true"><svg viewBox="0 0 16 16"><ellipse cx="8" cy="4" rx="5" ry="2"/><path d="M3 4v8c0 2 10 2 10 0V4M3 8c0 2 10 2 10 0"/></svg></span><h2 id="usage-intro-title"></h2></div><div class="intro-copy"><p id="usage-intro-history"></p><p id="usage-intro-scope"></p><p id="usage-intro-storage"></p></div><div class="intro-bottom"><span id="usage-intro-error" role="status"></span><button id="usage-intro-done" type="button"></button></div>');
  page.querySelector('.top').after(intro);
  css.textContent+=`
    .usage-intro{margin:18px 0 0;padding:17px 20px 14px;border:1px solid var(--pulse-border);border-radius:12px;background:var(--pulse-control)}.usage-intro[hidden]{display:none}
    .intro-heading{display:flex;align-items:center;gap:9px;margin-bottom:9px}.intro-heading h2{font-size:13px;font-weight:550;margin:0}.intro-mark{display:flex;color:var(--pulse-accent)}.intro-mark svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.2;stroke-linecap:round;stroke-linejoin:round}
    .intro-copy{display:grid;gap:5px;color:var(--pulse-muted);font-size:11px;line-height:1.65}.intro-copy p{margin:0}.intro-bottom{display:flex;justify-content:flex-end;align-items:center;gap:14px;margin-top:11px}.intro-bottom span{margin-right:auto;color:var(--pulse-warning);font-size:11px}
    #usage-intro-done{padding:6px 13px;min-height:30px;border:1px solid var(--pulse-border);border-radius:7px;background:var(--pulse-hover);color:var(--pulse-foreground);font:inherit;font-size:11px;cursor:pointer;transition:background-color 140ms ease,transform 120ms ease}#usage-intro-done:hover{background:var(--pulse-selected)}#usage-intro-done:active{transform:scale(.98)}#usage-intro-done:disabled{opacity:.55;cursor:wait}
    @media(max-width:520px){.usage-intro{padding:14px}.intro-bottom{align-items:flex-start}.intro-bottom span{line-height:1.5}}
  `;
  const $=id=>view.getElementById(id),text=(id,value)=>{if($(id).textContent!==value)$(id).textContent=value;};
  let value=null,tab='overview',heatMode='day',period='day',year=null,anchor=null,selected=null,disabledModels=new Set(),lastKey='',busy=false,opener=null;
  let disposed=false,refreshMotion=null,refreshDelay=null,finishRefresh=null,accountKey=null,tipTarget=null,tipModel=null;
  const zh=()=>language.language==='zh-CN'||language.language==='zh-TW',tw=()=>language.language==='zh-TW',w=(cn,en,twText)=>(tw()&&twText!==undefined)?twText:(zh()?cn:en);
  let guideSaving=false,guideError=false,guideSignature=null;
  const replayGuide=window.__agPulseUsageGuidePreview===true;
  function renderGuide(){
    const signature=language.language+'|'+themeSignature();
    if(replayGuide&&signature!==guideSignature){guideDismissed=false;guideError=false;}
    guideSignature=signature;intro.hidden=guideDismissed;
    text('usage-intro-title',w('先了解你的用量统计','About your token usage','先了解您的用量統計'));
    text('usage-intro-history',w('自动汇总当前账号可读取的本地历史对话，再持续记录新请求；已删除或缺失的历史可能无法补齐。','Available local conversations for this account are imported automatically, then new requests are recorded. Deleted or missing history may leave gaps.','自動彙總目前帳號可讀取的本機歷史對話，並持續記錄新請求；已刪除或缺失的記錄可能無法補齊。'));
    text('usage-intro-scope',w('统计仅代表本机已记录的 Token 用量，不是账户账单；天、周、月均按 UTC+8 划分。','Totals cover usage recorded on this device, not account billing. Days, weeks and months use UTC+8.','統計僅代表本機已記錄的 Token 用量，非帳號帳單；日、週、月均按 UTC+8 劃分。'));
    text('usage-intro-storage',w('只在本地保存时间、模型和用量，不保存对话正文。删除对话不会扣除已记录的用量。','Only times, models and usage counters are saved locally, never conversation text. Deleting a chat does not subtract usage already recorded.','僅於本機儲存時間、模型與用量，不儲存對話內文。刪除對話不會扣減已記錄的用量。'));
    text('usage-intro-done',guideSaving?w('保存中…','Saving…','儲存中…'):w('知道了','Got it','我知道了'));
    text('usage-intro-error',guideError?w('未能保存，请再试一次。','Could not save. Please try again.','未能儲存，請再試一次。'):'' );
    $('usage-intro-done').disabled=guideSaving;$('usage-intro-done').setAttribute('aria-busy',String(guideSaving));
  }
  function dismissGuide(){
    if(disposed)return;const focused=view.activeElement===$('usage-intro-done');guideDismissed=true;renderGuide();
    if(focused&&dialog.open)$('overview-tab').focus({preventScroll:true});
  }
  $('usage-intro-done').addEventListener('click',async()=>{
    if(guideSaving||disposed)return;guideSaving=true;guideError=false;renderGuide();
    try{await onDismissGuide();dismissGuide();}catch{if(!disposed)guideError=true;}
    finally{guideSaving=false;if(!disposed)renderGuide();}
  });
  const full=n=>Number(n||0).toLocaleString(language.language==='en'?'en-US':language.language);
  const compact=n=>{n=Number(n||0);const limits=[[1e9,'B'],[1e6,'M'],[1e3,'K']];for(const [base,suffix]of limits)if(n>=base)return (n/base).toFixed(1).replace(/\.0$/,'')+suffix;return full(n);};
  const add=(date,days)=>{const d=new Date(date+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);};
  const week=date=>{const d=new Date(date+'T00:00:00Z');return add(date,-((d.getUTCDay()+6)%7));};
  const month=(date,shift)=>{const d=new Date(date.slice(0,7)+'-01T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+shift);return d.toISOString().slice(0,10);};
  const modelName=model=>model.replace(/-n$/,'').replace(/^gemini-/i,'Gemini ').replace(/^claude-/i,'Claude ').replace(/^gpt-/i,'GPT ').replace(/-/g,' ');
  const themeSignature=()=>{const s=getComputedStyle(root.host||dialog);return [s.getPropertyValue('--pulse-accent'),s.getPropertyValue('--pulse-background'),root.host?.dataset.pulseTheme].join('|');};
  let paletteKey='',modelColors=new Map();
  const colorCanvas=document.createElement('canvas');colorCanvas.width=colorCanvas.height=1;
  const colorContext=colorCanvas.getContext('2d',{willReadFrequently:true});
  const rgb=css=>{colorContext.clearRect(0,0,1,1);colorContext.fillStyle='#000';colorContext.fillStyle=css;colorContext.fillRect(0,0,1,1);return [...colorContext.getImageData(0,0,1,1).data].slice(0,3);};
  const luminance=a=>a.reduce((sum,v,i)=>{v/=255;return sum+(v<=.04045?v/12.92:((v+.055)/1.055)**2.4)*[.2126,.7152,.0722][i];},0);
  const contrast=(a,b)=>(Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
  const hsl=a=>{const [r,g,b]=a.map(v=>v/255),hi=Math.max(r,g,b),lo=Math.min(r,g,b),d=hi-lo,l=(hi+lo)/2;return [d?((hi===r?(g-b)/d+(g<b?6:0):hi===g?(b-r)/d+2:(r-g)/d+4)*60):0,d?d/(1-Math.abs(2*l-1)):0,l];};
  const fromHsl=(h,s,l)=>{const a=s*Math.min(l,1-l),f=n=>{const k=(n+h/30)%12;return Math.round(255*(l-a*Math.max(-1,Math.min(k-3,9-k,1))));};return [f(0),f(8),f(4)];};
  function syncPalette(){
    const models=[...(value?.models||[])].sort(),key=themeSignature()+'|'+models.join('|');if(key===paletteKey)return;paletteKey=key;modelColors.clear();
    const style=getComputedStyle(root.host||dialog),base=rgb(style.getPropertyValue('--pulse-accent').trim()||'#85a8ff'),background=rgb(style.getPropertyValue('--pulse-background').trim()||'#1c1d1f'),[h,s]=hsl(base);
    // An analogous scale stays harmonious as the host accent changes. Tonal
    // variation distinguishes adjacent series without provider brand colors.
    const dark=luminance(background)<.35,offsets=[0,-18,18,-36,36,-9,9,-27,27],tones=dark?[.64,.52,.73,.59,.68]:[.43,.33,.51,.38,.47];
    const end=contrast([255,255,255],background)>contrast([0,0,0],background)?1:0;
    models.forEach((model,i)=>{const hue=(h+offsets[i%offsets.length]+360)%360,saturation=s<.08?.07:Math.max(.28,Math.min(.55,s*.72));let lightness=tones[i%tones.length],c=fromHsl(hue,saturation,lightness);
      // Chart marks (including small legend dots) need contrast on the actual
      // custom background, rather than relying solely on dark/light labels.
      for(let step=0;contrast(c,background)<3&&step<100;step++){lightness+=end? .005:-.005;lightness=Math.max(0,Math.min(1,lightness));c=fromHsl(hue,saturation,lightness);}
      modelColors.set(model,'rgb('+c.join(' ')+')');
    });
  }
  const color=model=>modelColors.get(model)||'var(--pulse-accent)';
  const totals=(from,to,filter=false)=>{
    const models={};for(const day of value?.days||[])if(day.date>=from&&day.date<=to)for(const [model,r]of Object.entries(day.models)){
      if(filter&&disabledModels.has(model))continue;
      models[model]||={total:0,requests:0,uncached:0,cacheRead:0,cacheWrite:0,output:0};for(const key of Object.keys(models[model]))models[model][key]+=r[key]||0;
    }
    return {from,to,models,total:Object.values(models).reduce((n,r)=>n+r.total,0),requests:Object.values(models).reduce((n,r)=>n+r.requests,0)};
  };
  const node=(tag,className,content)=>{const n=document.createElement(tag);if(className)n.className=className;if(content!==undefined)n.textContent=content;return n;};
  function tooltip(bucket,target,activeModel=null){
    if(!$('tip').hidden&&tipTarget===target&&tipModel===activeModel)return;tipTarget=target;tipModel=activeModel;
    highlightModel(activeModel);
    const tip=$('tip');tip.replaceChildren(node('div','tip-title',bucket.from===bucket.to?bucket.from:bucket.from+' – '+bucket.to),node('strong','',full(bucket.total)+' Token'),node('div','muted',w(`${bucket.requests} 次请求`,`${bucket.requests} requests`,`${bucket.requests} 次請求`)));
    for(const [model,r]of Object.entries(bucket.models).sort((a,b)=>b[1].total-a[1].total)){
      const row=node('div','tip-model'+(activeModel?(activeModel===model?' active':' dimmed'):'')),label=node('span',''),dot=node('i','dot'),amount=node('span','',compact(r.total));dot.style.setProperty('--model-color',color(model));label.append(dot,document.createTextNode(modelName(model)));amount.append(node('span','model-share',bucket.total?(r.total/bucket.total*100).toFixed(1)+'%':'0%'));row.append(label,amount);tip.append(row);
    }
    tip.hidden=false;const rect=target.getBoundingClientRect(),bounds=dialog.getBoundingClientRect(),r=tip.getBoundingClientRect();
    tip.style.left=Math.min(bounds.right-r.width-12,Math.max(bounds.left+12,rect.left+rect.width/2-r.width/2))+'px';
    tip.style.top=Math.max(bounds.top+12,rect.top-r.height-10)+'px';
  }
  const bindBucket=(button,bucket)=>{
    button.setAttribute('aria-label',(bucket.from===bucket.to?bucket.from:bucket.from+' – '+bucket.to)+': '+full(bucket.total)+' Token');
    button.addEventListener('pointerenter',()=>tooltip(bucket,button));button.addEventListener('pointerleave',()=>{$('tip').hidden=true;highlightModel(null);});button.addEventListener('focus',()=>tooltip(bucket,button));button.addEventListener('blur',()=>{$('tip').hidden=true;highlightModel(null);});
    button.addEventListener('pointermove',event=>{const model=event.target.closest?.('.bar-segment')?.dataset.model||null;tooltip(bucket,button,model);});
    button.addEventListener('click',()=>{selected=bucket;anchor=bucket.from;showSelection();});
  };
  function showSelection(){const bucket=selected||totals(value.today,value.today);text('selection-title',bucket.from===bucket.to?bucket.from:bucket.from+' – '+bucket.to);text('selection-value',full(bucket.total)+' Token · '+w(`${bucket.requests} 次请求`,`${bucket.requests} requests`,`${bucket.requests} 次請求`));}
  function renderHeat(){
    if(!value)return;
    const start=week(year+'-01-01'),end=year+'-12-31',weeks=Math.floor((Date.parse(end)-Date.parse(start))/604800000)+1;
    $('heat').replaceChildren();$('months').replaceChildren();$('weekdays').replaceChildren();$('heat').className='heat'+(heatMode==='week'?' week':'');
    $('heat').style.gridTemplateColumns=`repeat(${weeks},minmax(0,1fr))`;
    if(heatMode==='week')$('heat').style.setProperty('grid-template-columns',`repeat(${Math.ceil(weeks/2)},minmax(0,1fr))`,'important');
    const buckets=[];for(let i=0;i<(heatMode==='day'?weeks*7:weeks);i++){
      const date=add(start,heatMode==='day'?i:i*7),to=heatMode==='day'?date:add(date,6);
      buckets.push(heatMode==='day'?totals(date,date):totals(date<year+'-01-01'?year+'-01-01':date,to>end?end:to));
    }
    const max=Math.max(1,...buckets.map(b=>b.total));
    for(const bucket of buckets){
      const button=node('button','');button.type='button';const future=bucket.from>value.today||bucket.to<year+'-01-01'||bucket.from>year+'-12-31';
      button.dataset.level=bucket.total===0?'0':String(Math.min(4,Math.ceil(bucket.total/max*4)));if(future){button.className='future';button.disabled=true;}
      if(!future)bindBucket(button,bucket);button.tabIndex=-1;$('heat').append(button);
    }
    const usable=[...$('heat').children].filter(b=>!b.disabled),lastActive=[...$('heat').children].reverse().find(b=>!b.disabled&&b.dataset.level!=='0');
    if(usable.length)(lastActive||usable.at(-1)).tabIndex=0;
    if(heatMode==='day'){
      $('months').style.gridTemplateColumns=`repeat(${weeks},minmax(0,1fr))`;
      for(let m=1;m<=12;m++){const date=`${year}-${String(m).padStart(2,'0')}-01`,col=Math.floor((Date.parse(date)-Date.parse(start))/604800000)+1;
        const label=node('span','',zh()?m+'月':['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1]);label.style.gridColumn=col;label.style.gridRow=1;$('months').append(label);}
      for(let i=0;i<7;i++)$('weekdays').append(node('span','',i%2===0?(zh()?['一','','三','','五','','日'][i]:['M','','W','','F','','S'][i]):''));
    }
    text('heat-sub',heatMode==='day'?w('每格代表一天','Each square is one day','每格代表一天'):w('每格代表一周 · 周一开始','Each square is one week · starts Monday','每格代表一週 · 週一開始'));
    const annual=totals(year+'-01-01',year+'-12-31');text('heat-summary',w(`${year} 年 · ${full(annual.total)} Token`,`${year} · ${full(annual.total)} tokens`,`${year} 年 · ${full(annual.total)} Token`));
    for(const b of view.querySelectorAll('[data-heat]'))b.setAttribute('aria-pressed',String(b.dataset.heat===heatMode));showSelection();
  }
  function highlightModel(model){
    if(model)$('plot').dataset.highlight=model;else delete $('plot').dataset.highlight;
    for(const bar of $('plot').querySelectorAll('.bar-segment')){if(model&&bar.dataset.model===model)bar.dataset.highlight='true';else delete bar.dataset.highlight;}
  }
  const chartSummary=node('div','chart-summary');$('detail-title').after(chartSummary);
  const chartHeading=node('div','');$('detail-title').before(chartHeading);chartHeading.append($('detail-title'),chartSummary);
  function renderChart(){
    if(!value)return;syncPalette();$('tip').hidden=true;highlightModel(null);
    const buckets=[];
    if(period==='day'){const start=month(anchor,0),end=add(month(anchor,1),-1);for(let date=start;date<=end;date=add(date,1))buckets.push(totals(date,date,true));text('range-label',start.slice(0,7));}
    else if(period==='week'){const start=add(week(anchor),-11*7);for(let i=0;i<12;i++){const from=add(start,i*7);buckets.push(totals(from,add(from,6),true));}text('range-label',start.slice(5)+' – '+add(week(anchor),6).slice(5));}
    else{for(let i=-11;i<=0;i++){const from=month(anchor,i);buckets.push(totals(from,add(month(from,1),-1),true));}text('range-label',buckets[0].from.slice(0,7)+' – '+month(anchor,0).slice(0,7));}
    $('next').disabled=period==='week'?week(anchor)>=week(value.today):anchor.slice(0,7)>=value.today.slice(0,7);$('legend').replaceChildren();
    for(const model of value.models){const button=node('button',''),dot=node('i','dot');dot.style.setProperty('--model-color',color(model));button.append(dot,document.createTextNode(modelName(model)));button.type='button';button.setAttribute('aria-pressed',String(!disabledModels.has(model)));button.addEventListener('click',()=>{if(disabledModels.has(model))disabledModels.delete(model);else disabledModels.add(model);renderChart();});button.addEventListener('pointerenter',()=>highlightModel(disabledModels.has(model)?null:model));button.addEventListener('pointerleave',()=>highlightModel(null));$('legend').append(button);}
    const max=Math.max(1,...buckets.map(b=>b.total)),ceiling=max>1?Math.ceil(max/(10**Math.floor(Math.log10(max))))*10**Math.floor(Math.log10(max)):1;
    $('axis').replaceChildren();$('plot').replaceChildren();
    for(let i=0;i<=4;i++){const label=node('span','',compact(ceiling*i/4));label.style.bottom=(19+(246-19)*i/4)+'px';$('axis').append(label);const line=node('i','grid-line');line.style.bottom=(19+(246-19)*i/4)+'px';$('plot').append(line);}
    for(const [i,bucket]of buckets.entries()){
      const button=node('button','bar-column');button.type='button';const stack=node('div','stack');
      const segments=value.models.filter(model=>bucket.models[model]?.total>0);
      // Continuous stack: rounding clips only its outer top corners. Internal
      // separators are inset, so small values and total heights remain exact.
      for(const [j,model]of segments.entries()){const r=bucket.models[model],bar=node('i','bar-segment'),height=r.total/ceiling*227;bar.dataset.model=model;bar.setAttribute('aria-hidden','true');bar.style.setProperty('--model-color',color(model));bar.style.height=height+'px';if(j&&height>=3)bar.style.boxShadow='inset 0 -1px 0 color-mix(in srgb,var(--pulse-background) 48%,transparent)';stack.append(bar);}
      if(!bucket.total)stack.append(node('i','empty-bar'));button.append(stack);
      if(period!=='day'||i%3===0||i===buckets.length-1)button.append(node('span','x-label',period==='day'?String(i+1):period==='week'?bucket.from.slice(5):bucket.from.slice(0,7)));
      bindBucket(button,bucket);$('plot').append(button);
    }
    if(!buckets.some(b=>b.total))$('plot').append(node('div','chart-empty',w('所选时段暂无用量记录','No usage recorded in this period','所選時段尚無用量記錄')));
    $('table-head').replaceChildren(...[w('模型','Model','模型'),w('总 Token','Total tokens','總 Token'),w('未缓存输入','Uncached input','未快取輸入'),w('缓存读取','Cache read','快取讀取'),w('缓存写入','Cache write','快取寫入'),w('输出','Output','輸出')].map(label=>node('th','',label)));
    $('table-body').replaceChildren();const rangeTotals=totals(buckets[0].from,buckets.at(-1).to,true);
    chartSummary.replaceChildren(node('strong','',compact(rangeTotals.total)+' Token'),document.createTextNode(' · '+w(`${full(rangeTotals.requests)} 次请求`,`${full(rangeTotals.requests)} requests`,`${full(rangeTotals.requests)} 次請求`)));
    for(const [model,r]of Object.entries(rangeTotals.models).sort((a,b)=>b[1].total-a[1].total)){
      const row=node('tr',''),label=node('td',''),dot=node('span','dot');dot.style.setProperty('--model-color',color(model));label.append(dot,document.createTextNode(modelName(model)));row.append(label,...[r.total,r.uncached,r.cacheRead,r.cacheWrite,r.output].map(n=>node('td','',full(n))));$('table-body').append(row);
    }
    for(const b of view.querySelectorAll('[data-period]'))b.setAttribute('aria-pressed',String(b.dataset.period===period));
  }
  function render(){
    renderGuide();
    if(!value){
      closeYear(false);$('tip').hidden=true;$('overview').hidden=true;$('details').hidden=true;$('usage-waiting').hidden=false;
      text('usage-waiting',w('正在重新连接统计…','Reconnecting usage…','正在重新連線統計資料…'));text('subtitle',w('正在重新连接本机统计','Reconnecting local usage','正在重新連線本機統計'));text('coverage','');text('timezone','');$('alert').hidden=true;
      for(const metric of $('totals').children){metric.title='';metric.querySelector('.value')?.replaceChildren(node('span','','—'));}
      return;
    }
    $('usage-waiting').hidden=true;
    syncPalette();
    text('title',w('用量统计','Token usage','用量統計'));dialog.setAttribute('aria-label',w('用量统计','Token usage','用量統計'));text('subtitle',w(`本机 ${hostLabel} · 当前账号`,`Local ${hostLabel} · current account`,`本機 ${hostLabel} · 目前帳號`));
    text('overview-tab',w('活动概览','Activity','活動總覽'));text('details-tab',w('用量详情','Usage details','用量詳細資料'));text('activity-title',w('Token 活动','Token activity','Token 活動'));text('detail-title',w('按模型统计','Usage by model','依模型統計'));
    languagePicker.update();for(const [id,label]of [['locale',language.t('language')],['refresh',w('刷新用量','Refresh usage','重新整理用量')],['close',w('关闭','Close','關閉')]]){$(id).setAttribute('aria-label',label);$(id).title=label;}text('less',w('少','Less','少'));text('more',w('多','More','多'));text('selection-details',w('查看这段用量 →','View usage →','檢視此時段用量 →'));
    for(const b of view.querySelectorAll('[data-heat]'))b.textContent=b.dataset.heat==='day'?w('每天','Daily','每日'):w('每周','Weekly','每週');
    for(const b of view.querySelectorAll('[data-period]'))b.textContent=({day:w('天','Day','日'),week:w('周','Week','週'),month:w('月','Month','月')})[b.dataset.period];
    $('overview-tab').setAttribute('aria-selected',String(tab==='overview'));$('details-tab').setAttribute('aria-selected',String(tab==='details'));$('overview').hidden=tab!=='overview';$('details').hidden=tab!=='details';
    $('totals').replaceChildren();for(const [label,total]of [[w('今日用量','Today','今日用量'),value.todayTokens],[w('本周用量','This week','本週用量'),value.weekTokens],[w('本月用量','This month','本月用量'),value.monthTokens],[w('累计用量','All time','累積用量'),value.totalTokens]]){
      const metric=node('div','metric'),n=node('div','value',compact(total));n.append(node('span','unit','Token'));metric.append(node('label','',label),n);metric.title=full(total)+' Token';$('totals').append(metric);
    }
    const years=[];const first=Number(value.firstDate?.slice(0,4)||value.today.slice(0,4)),currentYear=Number(value.today.slice(0,4)),minimum=Math.max(first,currentYear-10);for(let y=currentYear;y>=minimum;y--)years.push(y);
    if($('year').dataset.years!==years.join(',')){
      $('year-menu').replaceChildren(...years.map(y=>{const option=node('button','year-option');option.type='button';option.dataset.year=String(y);option.setAttribute('role','option');option.tabIndex=-1;
        setMarkup(option,'<span></span><svg class="year-check" viewBox="0 0 16 16" aria-hidden="true"><path d="m3 8 3 3 7-7"/></svg>');option.firstElementChild.textContent=String(y);
        option.addEventListener('click',()=>{year=String(y);syncYear();closeYear();renderHeat();});return option;}));$('year').dataset.years=years.join(',');
    }
    syncYear();
    text('coverage',w(`已记录 ${full(value.requests)} 次请求${value.firstDate?' · 始于 '+value.firstDate:''}`,`${full(value.requests)} requests recorded${value.firstDate?' · since '+value.firstDate:''}`,`已記錄 ${full(value.requests)} 次請求${value.firstDate?' · 起始於 '+value.firstDate:''}`));
    text('timezone',value.timeZone+' · '+(value.syncing||value.retryingConversations>0?w('正在同步历史…','Syncing history…','正在同步歷程記錄…'):w('本地统计','Local usage','本機統計')));
    const alerts=[];if(value.unknownRequests)alerts.push(w(`${value.unknownRequests} 次请求日期未知，共 ${compact(value.unknownTokens)} Token`,`${value.unknownRequests} undated requests · ${compact(value.unknownTokens)} tokens`,`${value.unknownRequests} 次請求日期未知，共 ${compact(value.unknownTokens)} Token`));
    const confirmedMissing=value.confirmedMissingConversations??(value.syncing?0:value.missingConversations);
    if(value.partialRequests||value.unreadableFiles||confirmedMissing>0&&!value.syncing||value.persistenceError)alerts.push(w('部分记录暂不可读取，用量可能不完整','Some records are unavailable; usage may be incomplete','部分記錄暫無法讀取，用量可能不完整'));
    $('alert').hidden=!alerts.length;text('alert',alerts.join(' · '));
    if(tab==='overview')renderHeat();else renderChart();
  }
  function changeTab(next){closeYear(false);tab=next;$('tip').hidden=true;render();}
  $('overview-tab').addEventListener('click',()=>changeTab('overview'));$('details-tab').addEventListener('click',()=>changeTab('details'));
  for(const b of view.querySelectorAll('[data-heat]'))b.addEventListener('click',()=>{heatMode=b.dataset.heat;renderHeat();});
  for(const b of view.querySelectorAll('[data-period]'))b.addEventListener('click',()=>{period=b.dataset.period;renderChart();});
  function syncYear(){
    text('year-label',String(year));$('year').setAttribute('aria-label',w('选择年份','Select year','選取年份')+' · '+year);$('year-menu').setAttribute('aria-label',w('年份','Year','年份'));
    for(const option of $('year-menu').children)option.setAttribute('aria-selected',String(option.dataset.year===String(year)));
  }
  function closeYear(restore=true){if(!$('year-menu').matches(':popover-open'))return;$('year-menu').hidePopover();$('year').setAttribute('aria-expanded','false');if(restore)$('year').focus({preventScroll:true});}
  function positionYear(){
    if(!$('year-menu').matches(':popover-open'))return;const menu=$('year-menu'),r=$('year').getBoundingClientRect(),bounds=dialog.getBoundingClientRect(),width=menu.offsetWidth,height=menu.offsetHeight;
    menu.style.left=Math.max(bounds.left+12,Math.min(r.right-width,bounds.right-width-12))+'px';const below=r.bottom+7;
    menu.style.top=(below+height<=bounds.bottom-12?below:Math.max(bounds.top+12,r.top-height-7))+'px';
  }
  function openYear(){
    $('tip').hidden=true;$('year-menu').showPopover();$('year').setAttribute('aria-expanded','true');positionYear();
    ($('year-menu').querySelector('[aria-selected=true]')||$('year-menu').firstElementChild)?.focus({preventScroll:true});
  }
  $('year').addEventListener('click',()=>{$('year-menu').matches(':popover-open')?closeYear():openYear();});
  $('year').addEventListener('keydown',event=>{if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();openYear();if(event.key==='Home')$('year-menu').firstElementChild?.focus();if(event.key==='End')$('year-menu').lastElementChild?.focus();}});
  $('year-menu').addEventListener('keydown',event=>{
    const options=[...$('year-menu').children],current=options.indexOf(view.activeElement);let next=null;
    if(event.key==='ArrowDown')next=Math.min(options.length-1,current+1);else if(event.key==='ArrowUp')next=Math.max(0,current-1);else if(event.key==='Home')next=0;else if(event.key==='End')next=options.length-1;
    if(next!==null){event.preventDefault();options[next]?.focus({preventScroll:true});}else if(event.key==='Escape'){event.preventDefault();event.stopPropagation();closeYear();}else if(event.key==='Tab')closeYear();
  });
  view.addEventListener('pointerdown',event=>{const path=event.composedPath();if(!path.includes($('year'))&&!path.includes($('year-menu')))closeYear(false);});
  page.addEventListener('scroll',closeYearOnScroll,{passive:true});function closeYearOnScroll(){closeYear(false);}
  window.addEventListener('resize',positionYear);
  $('heat').addEventListener('keydown',event=>{
    const buttons=[...$('heat').children],index=buttons.indexOf(event.target);if(index<0)return;
    const delta=heatMode==='day'?{ArrowLeft:-7,ArrowRight:7,ArrowUp:-1,ArrowDown:1}:{ArrowLeft:-1,ArrowRight:1,ArrowUp:-Math.ceil(buttons.length/2),ArrowDown:Math.ceil(buttons.length/2)};
    let next=event.key==='Home'?buttons.findIndex(b=>!b.disabled):event.key==='End'?buttons.findLastIndex(b=>!b.disabled):index+(delta[event.key]??NaN);
    if(!Number.isFinite(next)||next<0||next>=buttons.length||buttons[next].disabled)return;event.preventDefault();event.target.tabIndex=-1;buttons[next].tabIndex=0;buttons[next].focus();
  });
  $('selection-details').addEventListener('click',()=>{anchor=(selected?.from||value.today);period=heatMode;changeTab('details');});
  for(const [id,step]of [['previous',-1],['next',1]])$(id).addEventListener('click',()=>{anchor=period==='day'?month(anchor,step):period==='week'?add(anchor,step*84):month(anchor,step*12);renderChart();});
  const languagePicker=language.mountLanguagePicker({button:$('locale'),label:$('locale-label'),parent:dialog,choose:onLanguage});
  $('refresh').addEventListener('click',async()=>{
    if(busy||disposed)return;busy=true;const button=$('refresh'),turn=600,started=performance.now();button.disabled=true;button.setAttribute('aria-busy','true');
    refreshMotion=button.querySelector('svg').animate([{transform:'rotate(0deg)'},{transform:'rotate(360deg)'}],{duration:turn,iterations:Infinity});
    try{await onRefresh();}
    catch{if(!disposed){text('alert',w('暂时无法刷新，请稍后重试','Refresh unavailable. Try again shortly.','暫時無法重新整理，請稍後重試'));$('alert').hidden=false;}}
    finally{
      // Fast requests still paint one whole turn. Slow requests finish their
      // current turn, so cancel never snaps a half-rotated icon back to zero.
      if(!disposed){const elapsed=performance.now()-started,remaining=Math.max(turn,Math.ceil(elapsed/turn)*turn)-elapsed;
        await new Promise(resolve=>{finishRefresh=resolve;refreshDelay=setTimeout(resolve,Math.max(0,remaining));});}
      clearTimeout(refreshDelay);refreshDelay=null;finishRefresh=null;refreshMotion?.cancel();refreshMotion=null;busy=false;
      if(!disposed){button.disabled=false;button.setAttribute('aria-busy','false');}
    }
  });
  // Native showModal()/close() changes inertness across the complete host DOM.
  // In long chats this alone can block Chromium for seconds. A top-layer
  // popover keeps the same backdrop without touching every background node.
  // Contain pointer, focus, Tab, Escape and scrolling explicitly instead.
  function present(){
    if(dialog.matches(':popover-open'))return;
    dialog.removeAttribute('open');dialog.showPopover();dialog.setAttribute('open','');
    $('locale').focus({preventScroll:true});
  }
  function conceal(){
    if(dialog.matches(':popover-open'))dialog.hidePopover();dialog.removeAttribute('open');
  }
  function close(){languagePicker.close(false);closeYear(false);conceal();$('tip').hidden=true;opener?.focus({preventScroll:true});}
  $('close').addEventListener('click',close);dialog.addEventListener('cancel',event=>{event.preventDefault();close();});dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)close();}});
  const contentKey=data=>JSON.stringify([{...data,updatedAt:undefined},language.language,themeSignature()]);
  const within=event=>event.composedPath().includes(dialog);
  function containFocus(event){if(!disposed&&dialog.open&&!within(event)){$('locale').focus({preventScroll:true});}}
  function containKeys(event){
    if(disposed||!dialog.open)return;
    if(event.key==='Escape'){
      event.preventDefault();event.stopImmediatePropagation();
      if($('year-menu').matches(':popover-open'))closeYear();else close();return;
    }
    if(event.key!=='Tab')return;
    // The year menu retains its own Tab dismissal; focus stays in the dialog.
    if($('year-menu').matches(':popover-open'))closeYear(false);
    const controls=[...view.querySelectorAll('button,input,select,a[href],[tabindex]')].filter(n=>n.tabIndex>=0&&!n.disabled&&n.getClientRects().length&&getComputedStyle(n).visibility!=='hidden');
    if(!controls.length){event.preventDefault();return;}
    const index=controls.indexOf(view.activeElement);
    if(index<0||event.shiftKey&&index===0||!event.shiftKey&&index===controls.length-1){
      event.preventDefault();event.stopImmediatePropagation();(event.shiftKey?controls.at(-1):controls[0]).focus({preventScroll:true});
    }
  }
  function containScroll(event){if(!disposed&&dialog.open&&!within(event))event.preventDefault();}
  function containPointer(event){
    if(disposed||!dialog.open)return;
    const r=dialog.getBoundingClientRect();
    const backdropHit=event.composedPath()[0]===dialog;
    if(!within(event)||backdropHit&&(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)){event.preventDefault();event.stopImmediatePropagation();if(event.type==='click')close();}
  }
  document.addEventListener('focusin',containFocus,true);document.addEventListener('keydown',containKeys,true);
  document.addEventListener('wheel',containScroll,{capture:true,passive:false});document.addEventListener('touchmove',containScroll,{capture:true,passive:false});
  for(const type of ['pointerdown','mousedown','click'])document.addEventListener(type,containPointer,true);
  // CSS surfaces update immediately; JS model colors must follow in the same
  // theme change, rather than waiting for the next metrics poll.
  const themeObserver=new MutationObserver(()=>{if(!disposed&&value&&dialog.open){const key=contentKey(value);if(key!==lastKey){lastKey=key;render();}}});
  if(root.host)themeObserver.observe(root.host,{attributes:true,attributeFilter:['data-pulse-theme','style']});
  return {open(data,trigger){if(!data||disposed)return;accountKey=data.accountKey;value=data;opener=trigger;year||=data.today.slice(0,4);anchor||=data.today;lastKey=contentKey(data);render();present();},
    update(data){if(disposed)return;if(!data){if(!value)return;value=null;lastKey='';if(dialog.open)render();return;}if(accountKey&&accountKey!==data.accountKey){selected=null;disabledModels.clear();year=data.today.slice(0,4);anchor=data.today;}accountKey=data.accountKey;value=data;if(!dialog.open)return;const key=contentKey(data);if(key===lastKey)return;lastKey=key;render();},
    restoreModal(){if(!disposed&&dialog.open&&dialog.isConnected&&!dialog.matches(':popover-open')){closeYear(false);present();}},
    close,syncGuideDismissed(){if(!replayGuide)dismissGuide();},dispose(){disposed=true;languagePicker.dispose();themeObserver.disconnect();clearTimeout(refreshDelay);finishRefresh?.();refreshMotion?.cancel();closeYear(false);window.removeEventListener('resize',positionYear);document.removeEventListener('focusin',containFocus,true);document.removeEventListener('keydown',containKeys,true);document.removeEventListener('wheel',containScroll,true);document.removeEventListener('touchmove',containScroll,true);for(const type of ['pointerdown','mousedown','click'])document.removeEventListener(type,containPointer,true);conceal();dialog.remove();backdrop.remove();},get isOpen(){return dialog.open;}};
});

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

var installAgPulseInlineWidget = function installAgPulseInlineWidget() {
  if (window.__agPulseInlineInstalled) return;
  const report=(stage,details={})=>window.agPulseHost?.report?.({stage,...details});
  if (!document.documentElement) {
    document.addEventListener('DOMContentLoaded',installAgPulseInlineWidget,{once:true});
    return;
  }
  if (!window.agPulseHost) return;
  const localGet=key=>{try{return localStorage.getItem(key);}catch{return null;}};
  const localSet=(key,value)=>{try{localStorage.setItem(key,value);}catch{}};
  const language=window.__agPulseI18nFactory(localGet('ag-pulse-language'));
  const theme=window.__agPulseThemeFactory();
  const t=language.t;
  window.__agPulseInlineInstalled=true;
  report('boot',{hostFound:true});
  const ID='ag-pulse-status-bar';
  // Host-specific discovery stays outside the shared widget. The IDE has no
  // /c/<id> URL, and must never inherit the desktop's conversation fallback.
  const surface=window.__agPulseSurface;
  const setMarkup=(element,markup)=>{if(surface?.setMarkup)surface.setMarkup(element,markup);else element.innerHTML=markup;};
  let node=null,root=null,data=null,pending=false,cardName=null,hoverTimer=null,openTimer=null,warmUntil=0,lastConversation=null,lastFetch=0,lastExpiredRefresh=0,resizeObserver=null,groupMenu=null,themeController=null,changingCards=false;
  const HOVER_DELAY=250,WARM_WINDOW=350,LEAVE_DELAY=120;
  const isWarm=()=>Boolean(cardName||Date.now()<warmUntil);
  let chosen=localGet('ag-pulse-group'),group=null;
  let refreshRequest=null,manualRequest=null,requestEpoch=0,disposed=false;
  let composer=null,layoutFrame=null;
  let usageDashboard=null,updateMenu=null;
  let densityFrame=null,densityMotion=null,densityProbe=null;
  const densityMedia=matchMedia('(prefers-reduced-motion: reduce)');
  const densityEase='cubic-bezier(0.32,0.72,0,1)';
  let guideReady=false,guideDismissed=false,guideOpened=false,guideSaving=false,guideError=false,usageGuideDismissed=false;
  function syncGuide(value){if(value?.languageGuideDismissed===true)guideDismissed=true;if(value?.usageGuideDismissed===true){usageGuideDismissed=true;usageDashboard?.syncGuideDismissed();}}
  const preferences=language.connectPreferences({
    read:async()=>{const value=await window.agPulseHost.getPreferences();syncGuide(value);return value;},
    write:async input=>{const value=await window.agPulseHost.setPreferences(input);syncGuide(value);return value;},
    cache:value=>localSet('ag-pulse-language',value),changed:()=>{if(root){localize();render();tick();position();}},
  });
  void preferences.ready.then(()=>{if(disposed)return;guideReady=!preferences.error;scheduleLayout();});
  const icon=(name)=>({speed:'<path d="M3 12a6 6 0 1 1 10 0M8 9l3-4"/>',cache:'<ellipse cx="8" cy="4" rx="5" ry="2"/><path d="M3 4v8c0 2 10 2 10 0V4M3 8c0 2 10 2 10 0"/>',five:'<circle cx="8" cy="8" r="5.6"/><path d="M8 4.7v3.6l2.3 1.4"/>',week:'<rect x="2.5" y="3.5" width="11" height="10" rx="2"/><path d="M5 2v3m6-3v3M3 7h10"/>'}[name]);
  const svg=name=>`<svg viewBox="0 0 16 16" aria-hidden="true">${name==='context'?'<circle cx="8" cy="8" r="5.6"/><path d="M8 2.4V8l4.8 2.8"/>':icon(name)}</svg>`;
  const pct=n=>typeof n==='number'&&Number.isFinite(n)?`${(n*100).toFixed(1)}%`:'—';
  const rate=n=>typeof n==='number'&&Number.isFinite(n)?n.toLocaleString('en-US',{maximumFractionDigits:1,minimumFractionDigits:1}):'—';
  const count=n=>typeof n==='number'&&Number.isFinite(n)?n.toLocaleString('en-US'):'—';
  const compact=n=>typeof n!=='number'||!Number.isFinite(n)?'—':n>=1e9?`${(n/1e9).toFixed(1).replace(/\.0$/,'')}B`:n>=1e6?`${(n/1e6).toFixed(1).replace(/\.0$/,'')}M`:n>=1e3?`${(n/1e3).toFixed(1).replace(/\.0$/,'')}K`:String(n);
  const seconds=language.elapsed;
  const timer=(at,compact=false)=>language.countdown(at,Date.now(),compact);
  const date=language.resetDate;
  const label=g=>/gemini/i.test(g?.name||'')?'Gemini':/claude|gpt/i.test(g?.name||'')?'Claude / GPT':g?.name||t('group');
  const $=id=>root?.getElementById(id);
  const text=(id,value)=>{const e=$(id);if(e&&e.textContent!==String(value))e.textContent=String(value);};
  const attribute=(element,name,value)=>{if(value===null){if(element.hasAttribute(name))element.removeAttribute(name);}else if(element.getAttribute(name)!==String(value))element.setAttribute(name,String(value));};
  const style=(element,name,value)=>{if(element.style.getPropertyValue(name)!==value)element.style.setProperty(name,value);};
  const hidden=(element,value)=>{if(element.hidden!==value)element.hidden=value;};
  const GUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const conversationId=()=>{
    if(surface?.conversationId){
      const cid=surface.conversationId(composer);
      if(cid)return cid;
    }
    // Nested agents need not change the main window route. Read only the
    // nearest owner of this exact composer, never a sidebar/global chat ID.
    const owner=(composer?.box||composer?.row)?.closest('[data-cascade-id]');
    if(owner){const id=owner.getAttribute('data-cascade-id');return GUID.test(id||'')?id:null;}
    return location.pathname.match(/\/c\/([0-9a-f-]{36})/i)?.[1]||null;
  };
  function syncConversation(){
    const id=conversationId();
    if(id===lastConversation)return false;
    lastConversation=id;requestEpoch++;pending=false;refreshRequest=null;lastFetch=0;
    stopDensityMotion();densityFrame=null;densityProbe=null;
    manualRequest=null;refreshBusy(false);
    data={connection:'offline',groups:[],speed:null};group=null;hide();
    // Navigation has its own refresh budget. A request from the old composer
    // must neither block the new route nor reset its polling clock on arrival.
    queueMicrotask(()=>{if(!disposed)refresh();});return true;
  }
  function localize(){
    attribute(node,'lang',language.language);
    for(const e of root.querySelectorAll('[data-i18n]')){const value=t(e.dataset.i18n);if(e.textContent!==value)e.textContent=value;}
    for(const e of root.querySelectorAll('[data-i18n-aria]'))attribute(e,'aria-label',t(e.dataset.i18nAria));
    for(const e of root.querySelectorAll('[data-i18n-aria][title]'))attribute(e,'title',t(e.dataset.i18nAria));
    for(const button of root.querySelectorAll('[data-language-choice]')){attribute(button,'aria-pressed',button.dataset.languageChoice===language.language);attribute(button,'data-save-failed',preferences.error);attribute(button,'title',preferences.error?t('languageSaveFailed'):button.textContent);}
    text('language-save-note',preferences.error?t('languageSaveFailed'):'');
    const zh=language.language==='zh-CN',tw=language.language==='zh-TW';
    text('usage-today-label',tw?'今日用量':(zh?'今日用量':'Today'));text('usage-month-label',tw?'本月用量':(zh?'本月用量':'This month'));
    text('usage-open-label',tw?'檢視用量統計':(zh?'查看用量统计':'View token usage'));updateMenu?.localize();
    updateGuide();
  }
  function stopDensityMotion(){
    const motion=densityMotion;densityMotion=null;
    if(!motion)return;
    for(const animation of motion.animations)animation.cancel();
    motion.stage.remove();delete node?.dataset.motion;
  }
  function densitySnapshot(previous){
    const pieces=new Map();
    for(const chip of root.querySelectorAll('.bar .chip'))for(const element of chip.children){
      if(!element.getClientRects().length)continue;
      const style=getComputedStyle(element);
      pieces.set(element,{rect:element.getBoundingClientRect(),opacity:1,font:style.font,color:style.color,icon:element.matches('svg,.context-ring')});
    }
    // Read interrupted copies before changing density. Reading them after the
    // final flex layout moves their parent would bake that shift into the new
    // start position and produce a visible jump on reversal.
    if(previous&&densityMotion)for(const [element,visual]of densityMotion.pieces){
      const piece=pieces.get(element)||densityMotion.sources.get(element);
      if(piece)pieces.set(element,{...piece,rect:visual.getBoundingClientRect(),opacity:Number(getComputedStyle(visual).opacity)});
    }
    return {pieces,rect:node.getBoundingClientRect(),model:composer.model,modelRect:previous?.model===composer.model?previous.modelRect:composer.model?.getBoundingClientRect(),row:composer.row};
  }
  function densityBounds(next){
    const row=next.row.getBoundingClientRect(),target=next.rect;
    let left=Math.max(row.left,composer.anchor?.getBoundingClientRect().right||0),right=Math.min(row.right,innerWidth);
    for(const control of document.querySelectorAll('button,[role="button"],a[href],input,select')){
      if(control===next.model||next.model?.contains(control)||control.contains(next.model))continue;
      const r=control.getBoundingClientRect();
      if(r.width<=0||r.height<=0||Math.min(target.bottom,r.bottom)-Math.max(target.top,r.top)<=1)continue;
      if(control.closest('[hidden],[inert]')||getComputedStyle(control).visibility==='hidden')continue;
      if(!next.row.parentElement.contains(control)){
        if(Math.min(right,r.right)-Math.max(left,r.left)<=0)continue;
        const x=(Math.max(left,r.left)+Math.min(right,r.right))/2,y=(Math.max(target.top,r.top)+Math.min(target.bottom,r.bottom))/2;
        const hit=document.elementFromPoint(x,y);
        if(hit!==control&&!control.contains(hit))continue;
      }
      if(r.right<=target.left+1)left=Math.max(left,r.right);
      else if(r.left>=target.right-1)right=Math.min(right,r.left);
      else return null;
    }
    return right-left>=target.width-2?{left,right}:null;
  }
  function clipDensityMotion(next){
    if(!densityMotion)return;
    const bounds=densityBounds(next);
    if(!bounds){stopDensityMotion();return;}
    // The ribbon follows its parent 1:1 while dragging. Keep its existing
    // compositor animation and clock; only crop to current safe host bounds.
    const stage=densityMotion.stage,r=stage.getBoundingClientRect();
    stage.style.clipPath=`inset(0px ${Math.max(0,r.right-bounds.right)}px 0px ${Math.max(0,bounds.left-r.left)}px)`;
  }
  function animateDensity(previous,next){
    // A narrow composer gives its space straight back to native controls. Only
    // inert visual copies move; the real icons immediately have safe hit boxes.
    // Copies share a clipped ribbon with the model selector's reveal, never the
    // send/mic/add controls. Neither flex widths nor host styles are animated.
    const interrupted=densityMotion;
    const modelOpacity=next.model?getComputedStyle(next.model).opacity:'1';
    stopDensityMotion();
    if(!Element.prototype.animate)return;
    const bounds=densityBounds(next);if(!bounds)return;
    const {left,right}=bounds,target=next.rect;
    const reduce=densityMedia.matches,duration=reduce?120:240;
    const stage=document.createElement('div');stage.className='density-stage';stage.inert=true;stage.setAttribute('aria-hidden','true');
    stage.style.cssText=`left:${left-target.left}px;top:0;width:${right-left}px;height:${target.height}px`;
    root.append(stage);
    const motion={stage,animations:[],pieces:new Map(),sources:new Map([...previous.pieces,...next.pieces])};densityMotion=motion;node.dataset.motion='density';
    const play=(element,frames,options={})=>{const animation=element.animate(frames,{duration,easing:densityEase,...options});motion.animations.push(animation);return animation;};
    for(const element of new Set([...previous.pieces.keys(),...next.pieces.keys()])){
      const from=previous.pieces.get(element),to=next.pieces.get(element),piece=to||from;
      const visual=element.cloneNode(true),end=to?.rect||from.rect;
      for(const part of [visual,...visual.querySelectorAll('*')])for(const attribute of [...part.attributes])if(attribute.name==='id'||attribute.name.startsWith('data-')||attribute.name.startsWith('aria-'))part.removeAttribute(attribute.name);
      const endX=Math.max(left,Math.min(right-end.width,end.left)),endY=end.top-target.top;
      visual.classList.add('density-piece');visual.style.cssText+=`;position:absolute;left:${endX-left}px;top:${endY}px;width:${end.width}px;height:${end.height}px;font:${piece.font};color:${piece.color};margin:0;pointer-events:none;display:block`;
      stage.append(visual);motion.pieces.set(element,visual);
      const start=from?.rect||end;
      const startX=Math.max(left,Math.min(right-start.width,start.left));
      const dx=reduce?0:startX-endX,dy=reduce?0:start.top-end.top;
      const startOpacity=from?.opacity??0,endOpacity=to?1:0;
      play(visual,[{transform:`translate(${dx}px,${dy}px)`,opacity:startOpacity},{transform:'translate(0,0)',opacity:endOpacity}],{fill:'both',...(piece.icon?{}:{duration:to?duration:80})});
      if(to)play(element,[{opacity:0},{opacity:0}],{fill:'both'});
    }
    // The host model name often goes from a caret to a full label as space is
    // returned. Let the outgoing labels leave before revealing that name.
    if(next.model&&previous.model===next.model&&(Math.abs(next.modelRect.width-previous.modelRect.width)>8||interrupted&&Number(modelOpacity)<.999)){
      play(next.model,[{opacity:interrupted?modelOpacity:0},{opacity:1}],{delay:reduce||interrupted?0:100,duration:reduce?120:interrupted?240:140,fill:'backwards'});
    }
    const finish=play(stage,[{opacity:1},{opacity:1}]);
    finish.onfinish=()=>{if(densityMotion===motion){stopDensityMotion();position();}};
  }
  function fit(){
    if(!node?.isConnected)return;
    // A modal owns input while open. Composer collision scans behind its
    // backdrop cannot improve its layout and can hide its hosting strip.
    if(usageDashboard?.isOpen){stopDensityMotion();return;}
    reserveNativeSpace();
    const bar=root.querySelector('.bar'),oldDensity=node.dataset.density,oldReady=node.dataset.layout==='ready';
    let previous=densityFrame;
    if(['compact','narrow','context-only'].some(c=>node.classList.contains(c)))node.classList.remove('compact','narrow','context-only');
    // Flex shrink alone does not constrain nowrap children or protect controls
    // positioned outside the flex flow (e.g. Agent Manager window buttons).
    const fits=()=>{
      const rect=node.getBoundingClientRect(),row=composer.row.getBoundingClientRect();
      const intersects=other=>Math.min(rect.right,other.right)-Math.max(rect.left,other.left)>1&&Math.min(rect.bottom,other.bottom)-Math.max(rect.top,other.top)>1;
      if(bar.scrollWidth>bar.clientWidth+2||rect.width<=0||rect.left< -1||rect.right>innerWidth+1||rect.top< -1||rect.bottom>innerHeight+1||rect.left<row.left-1||rect.right>row.right+1)return false;
      if(!nativeComfortable())return false;
      if(composer.kind==='subagent'&&intersects(composer.anchor.getBoundingClientRect()))return false;
      for(const control of document.querySelectorAll('button,[role="button"],a[href],input,select,[contenteditable="true"]')){
        const other=control.getBoundingClientRect();
        if(other.width<=0||other.height<=0||!intersects(other))continue;
        if(control.closest('[hidden],[inert]')||getComputedStyle(control).visibility==='hidden')continue;
        // Scrolling messages can put clipped/covered links underneath the
        // fixed composer. Their rectangles alone are not a visible collision.
        // Always reserve local actions; other controls must actually paint at
        // the intersection (e.g. a floating jump-to-bottom button).
        if(composer.row.parentElement.contains(control))return false;
        const left=Math.max(rect.left,other.left),right=Math.min(rect.right,other.right),top=Math.max(rect.top,other.top),bottom=Math.min(rect.bottom,other.bottom);
        for(const [x,y]of [[(left+right)/2,(top+bottom)/2],[left+.5,top+.5],[right-.5,top+.5],[left+.5,bottom-.5],[right-.5,bottom-.5]]){
          const hit=document.elementFromPoint(x,y);
          if(hit===control||control.contains(hit))return false;
        }
      }
      return true;
    };
    let safe=fits();
    const rowWidth=composer.row.getBoundingClientRect().width;
    const probeKey=()=>node.style.cssText.replace(/--pulse-native-room:[^;]+;?/g,'')+'|'+language.language+'|'+lastConversation+'|'+bar.textContent+'|'+$('dot').className+'|'+getComputedStyle(composer.row).gap+'|'+Array.from(composer.row.querySelectorAll('button,[role="button"],a[href],input,select')).filter(c=>c!==composer.model&&!c.contains(composer.model)).map(c=>c.getBoundingClientRect().width).join(',');
    if(oldDensity==='icons'){
      const key=probeKey();
      // Twelve pixels of recovery headroom prevents threshold chatter. Shrinking
      // or scrolling in icon mode never toggles back to full just to measure it.
      if(!densityProbe||key!==densityProbe.key||rowWidth>=densityProbe.width+12){
        previous=densitySnapshot(previous);node.classList.remove('icons-only');safe=fits();
        if(!safe){node.classList.add('icons-only');safe=fits();densityProbe={key,width:rowWidth};}
        else densityProbe=null;
      }
    }else if(!safe){
      previous=densitySnapshot(previous);node.classList.add('icons-only');safe=fits();densityProbe={key:probeKey(),width:rowWidth};
    }
    node.dataset.density=node.classList.contains('icons-only')?'icons':'full';
    const state=safe?'ready':'blocked';
    if(node.dataset.layout!==state){node.dataset.layout=state;node.inert=!safe;if(!safe)hide();}
    const changed=safe&&oldReady&&previous?.row===composer.row&&oldDensity!==node.dataset.density;
    const next=changed?densitySnapshot():{rect:node.getBoundingClientRect(),model:composer.model,modelRect:composer.model?.getBoundingClientRect(),row:composer.row};
    if(changed)animateDensity(previous,next);
    else if(!safe||previous?.row!==composer.row||previous?.model!==composer.model)stopDensityMotion();
    else if(densityMotion)clipDensityMotion(next);
    densityFrame=next;
    updateGuide();
  }
  function badgeTextRects(badge){
    if(!badge?.isConnected)return [];
    const walker=document.createTreeWalker(badge,NodeFilter.SHOW_TEXT),range=document.createRange(),rects=[];
    for(let text=walker.nextNode();text;text=walker.nextNode()){
      if(!text.textContent.trim()||text.parentElement?.closest('svg,[hidden],[inert]')||getComputedStyle(text.parentElement).visibility==='hidden')continue;
      range.selectNodeContents(text);rects.push(...range.getClientRects());
    }
    return rects.filter(r=>r.width>0&&r.height>0);
  }
  function captureNative(found){
    const branch=found.branch,r=branch.getBoundingClientRect();
    const baseline={height:r.height,icons:Array.from(branch.querySelectorAll('svg')).map(icon=>({icon,width:icon.getBoundingClientRect().width})),reserve:0};
    if(found.kind==='ide'&&surface?.nativeReserve)baseline.reserve=surface.nativeReserve(found);
    if(found.kind==='subagent'){
      const badge=found.anchor,style=getComputedStyle(badge);
      // Summed glyph fragments recover intrinsic text width even if the host
      // is already wrapping the badge when we first attach.
      const textWidth=badgeTextRects(badge).reduce((sum,rect)=>sum+rect.width,0);
      const iconWidth=badge.querySelector('svg')?.getBoundingClientRect().width||0;
      const natural=textWidth+Math.max(iconWidth,12)+(parseFloat(style.columnGap)||0)+(parseFloat(style.paddingLeft)||0)+(parseFloat(style.paddingRight)||0);
      baseline.reserve=Math.ceil(Math.max(badge.getBoundingClientRect().width,natural)+badge.getBoundingClientRect().left-r.left+(parseFloat(getComputedStyle(branch).paddingRight)||0));
    }
    return baseline;
  }
  function nativeComfortable(){
    const baseline=composer.native;
    if(!baseline)return true;
    if(composer.branch.getBoundingClientRect().height>baseline.height+1)return false;
    if(baseline.icons.some(({icon,width})=>icon.isConnected&&icon.getBoundingClientRect().width<width-.5))return false;
    if(composer.kind==='ide'&&composer.branch.getBoundingClientRect().width<baseline.reserve-1)return false;
    if(composer.kind==='subagent'){
      if(composer.branch.getBoundingClientRect().width<baseline.reserve-1)return false;
      const lines=new Set(badgeTextRects(composer.anchor).map(r=>Math.round(r.top)));
      if(lines.size>1)return false;
    }
    return true;
  }
  function reserveNativeSpace(){
    if(!['subagent','ide'].includes(composer.kind)){if(node.style.getPropertyValue('--pulse-native-room'))node.style.removeProperty('--pulse-native-room');if(node.classList.contains('native-no-room'))node.classList.remove('native-no-room');return;}
    const row=composer.row,style=getComputedStyle(row),siblings=Array.from(row.children).filter(e=>e!==node&&e!==composer.branch&&e.getClientRects().length);
    const room=row.clientWidth-(parseFloat(style.paddingLeft)||0)-(parseFloat(style.paddingRight)||0)-composer.native.reserve-siblings.reduce((sum,e)=>{const s=getComputedStyle(e);return sum+e.getBoundingClientRect().width+(parseFloat(s.marginLeft)||0)+(parseFloat(s.marginRight)||0);},0)-(parseFloat(style.columnGap)||0)*(siblings.length+1)-10;
    const width=`${Math.max(0,Math.floor(room))}px`;if(node.style.getPropertyValue('--pulse-native-room')!==width)node.style.setProperty('--pulse-native-room',width);
    // A hidden ribbon must release its flex space as well as its hit targets.
    // The budget is independent of our own rectangle, so it recovers directly
    // when the sidebar is closed, without probing the native badge each frame.
    node.classList.toggle('native-no-room',room<76);
  }
  function scheduleLayout(){
    if(disposed||layoutFrame!==null)return;
    layoutFrame=requestAnimationFrame(()=>{layoutFrame=null;if(disposed)return;mount();fit();position();});
  }
  function observeComposer(){
    resizeObserver?.disconnect();
    resizeObserver??=new ResizeObserver(scheduleLayout);
    for(const element of new Set([node,composer.row,composer.row.parentElement,composer.branch,composer.editor]))resizeObserver.observe(element);
  }
  function composerLayout({row,editor,branch}){
    // Containment alone can join an app header and a distant message editor.
    // Accept only a horizontal, normal-flow action row local to that editor.
    const style=getComputedStyle(row);
    if(!['flex','inline-flex'].includes(style.display)||style.flexDirection!=='row'||['absolute','fixed'].includes(style.position)||row.closest('header,[role="banner"]'))return false;
    if(['absolute','fixed'].includes(getComputedStyle(branch).position))return false;
    const r=row.getBoundingClientRect(),e=editor.getBoundingClientRect(),p=row.parentElement.getBoundingClientRect();
    const gap=Math.max(0,r.top-e.bottom,e.top-r.bottom);
    const overlap=Math.min(r.bottom,e.bottom)-Math.max(r.top,e.top);
    return r.width>0&&r.height>0&&e.width>0&&e.height>0&&gap<=48&&overlap<=2&&Math.min(r.right,e.right)>Math.max(r.left,e.left)&&p.height<=e.height+r.height+96;
  }
  function closeGroup(){for(const e of root?.querySelectorAll('.group-menu')||[])e.hidden=true;for(const e of root?.querySelectorAll('.group-trigger')||[])e.setAttribute('aria-expanded','false');groupMenu=null;}
  // Pointer clicks and dialog focus restoration leave buttons focused after
  // the pointer departs. Only keyboard-visible focus keeps a card engaged.
  // The explicit first-use action moves focus into language choices. Keep
  // that guided destination available until the user chooses or leaves it.
  const cardEngaged=()=>Boolean(root?.activeElement?.matches(':focus-visible')||(guideOpened&&!guideDismissed&&cardName==='context'&&root?.activeElement?.matches('[data-language-choice]'))||groupMenu||node?.matches(':hover')||root?.querySelector('.card:not([hidden]):hover'));
  function cardVisibility(element,visible){
    if(visible){hidden(element,false);if(element.hasAttribute('popover')&&!element.matches(':popover-open'))element.showPopover();}
    else {if(element.hasAttribute('popover')&&element.matches(':popover-open'))element.hidePopover();hidden(element,true);}
  }
  function hide({keepWarm=false}={}){
    clearTimeout(openTimer);openTimer=null;
    clearTimeout(hoverTimer);hoverTimer=null;
    if(!keepWarm)warmUntil=0;
    changingCards=true;
    try{closeGroup();cardName=null;for(const e of root?.querySelectorAll('[data-card]')||[])e.setAttribute('aria-expanded','false');for(const e of root?.querySelectorAll('.card')||[])cardVisibility(e,false);}
    finally{changingCards=false;}
    updateGuide();
  }
  function show(name){
    if(disposed||!node?.isConnected||changingCards||usageDashboard?.isOpen||node.dataset.layout==='blocked')return;
    if(cardName!==name)closeGroup();
    clearTimeout(hoverTimer);hoverTimer=null;
    clearTimeout(openTimer);openTimer=null;
    cardName=name;warmUntil=0;
    for(const e of root.querySelectorAll('[data-card]'))e.setAttribute('aria-expanded',String(e.dataset.card===name));
    changingCards=true;
    try{for(const e of root.querySelectorAll('.card'))cardVisibility(e,e.id===`${name}-card`);}
    finally{changingCards=false;}
    updateGuide();
    position();
  }
  function hoverChip(name){
    clearTimeout(hoverTimer);
    if(isWarm()){
      clearTimeout(openTimer);openTimer=null;
      show(name);
    }else{
      clearTimeout(openTimer);
      const anchor=node,chip=root?.querySelector(`[data-card="${name}"]`),editor=composer?.editor,conversation=conversationId();
      openTimer=setTimeout(()=>{
        openTimer=null;
        // A host route/composer replacement can detach the chip without a
        // pointerleave. Never show a stale or disconnected top-layer popover.
        if(disposed||node!==anchor||!anchor?.isConnected||!chip?.isConnected||!chip.matches(':hover')||composer?.editor!==editor||conversationId()!==conversation)return;
        show(name);
      },HOVER_DELAY);
    }
  }
  function leaveChip(){
    clearTimeout(openTimer);openTimer=null;
  }
  function scheduleHide(){
    clearTimeout(openTimer);openTimer=null;
    clearTimeout(hoverTimer);
    // Measure the warm window from pointer departure, not the later hide.
    if(cardName)warmUntil=Date.now()+WARM_WINDOW;
    hoverTimer=setTimeout(()=>{hoverTimer=null;if(!cardEngaged())hide({keepWarm:true});},LEAVE_DELAY);
  }
  function position(){
    positionGuide();
    if(!cardName)return;
    const button=root.querySelector(`[data-card="${cardName}"]`),card=$(`${cardName}-card`),rect=button.getBoundingClientRect();
    const width=Math.min(310,window.innerWidth-24);style(card,'width',`${width}px`);
    const roomAbove=rect.top-21,roomBelow=window.innerHeight-rect.bottom-21;
    style(card,'overflow-y','auto');
    style(card,'left',`${Math.min(window.innerWidth-width-12,Math.max(12,rect.left+rect.width/2-width/2))}px`);
    // scrollHeight includes clipped content. Expanding maxHeight to measure it
    // on every poll used to reset scrollTop and then shrink the card again.
    const height=card.scrollHeight+card.offsetHeight-card.clientHeight;
    const useAbove=height<=roomAbove || roomAbove>=roomBelow;
    style(card,'max-height',`${Math.max(80,useAbove?roomAbove:roomBelow)}px`);
    style(card,'top',`${Math.max(12,useAbove?rect.top-card.offsetHeight-9:rect.bottom+9)}px`);
  }
  function positionGuide(){
    const tip=$('language-guide'),button=root?.querySelector('[data-card="context"]');
    if(!tip||tip.hidden||!button)return;
    const rect=button.getBoundingClientRect(),width=Math.min(244,innerWidth-24);
    style(tip,'width',`${width}px`);
    const left=Math.max(12,Math.min(innerWidth-width-12,rect.left+rect.width/2-width/2));
    style(tip,'left',`${left}px`);
    style(tip,'--guide-anchor',`${Math.max(16,Math.min(width-16,rect.left+rect.width/2-left))}px`);
    const above=rect.top-22,below=innerHeight-rect.bottom-22,height=tip.scrollHeight+tip.offsetHeight-tip.clientHeight,useAbove=height<=above||above>=below;
    style(tip,'max-height',`${Math.max(80,useAbove?above:below)}px`);
    style(tip,'top',`${Math.max(12,useAbove?rect.top-tip.offsetHeight-10:rect.bottom+10)}px`);
    attribute(tip,'data-side',useAbove?'above':'below');
  }
  function updateGuide(){
    const tip=$('language-guide');if(!tip)return;
    const tw=language.language==='zh-TW',hint=tip.querySelector('#guide-open span[lang]');
    const heading=tip.querySelector('.guide-heading strong span'),headingText=tw?'/ 語言':'/ 语言',hintText=tw?'在上下文詳細資料中切換語言':'在上下文详情中切换语言';
    if(heading.textContent!==headingText)heading.textContent=headingText;
    attribute(hint,'lang',tw?'zh-TW':'zh-CN');if(hint.textContent!==hintText)hint.textContent=hintText;
    attribute($('guide-close'),'aria-label',tw?'Dismiss language tip / 關閉語言提示':'Dismiss language tip / 关闭语言提示');
    const visible=!disposed&&guideReady&&!guideDismissed&&!guideOpened&&!cardName&&node?.isConnected&&['main','ide'].includes(composer?.kind)&&node.dataset.layout==='ready'&&node.style.visibility!=='hidden';
    const entering=visible&&tip.hidden;
    cardVisibility(tip,visible);
    const button=root.querySelector('[data-card="context"]');
    if(visible)button.setAttribute('aria-describedby','language-guide');else button.removeAttribute('aria-describedby');
    text('guide-save-note',guideError?(tw?'Could not save. Please retry. / 未能儲存，請重試。':'Could not save. Please retry. / 未能保存，请重试。'):'');
    $('guide-close').disabled=guideSaving;
    positionGuide();
    if(entering)tip.animate([{opacity:0,transform:`translateY(${tip.dataset.side==='above'?'4':'-4'}px)`},{opacity:1,transform:'translateY(0)'}],{duration:160,easing:'cubic-bezier(0.23,1,0.32,1)'});
  }
  async function dismissGuide(){
    if(guideSaving)return;guideSaving=true;guideError=false;updateGuide();
    try{const value=await window.agPulseHost.setPreferences({languageGuideDismissed:true});if(value?.languageGuideDismissed!==true||value.error)throw new Error('Guide not saved');syncGuide(value);preferences.sync(value);}
    catch{guideError=true;}
    finally{guideSaving=false;updateGuide();}
  }
  function findComposer(){
    if(surface?.findComposer){
      const custom=surface.findComposer(composer);
      if(custom)return custom;
    }
    const visible=element=>element.isConnected&&!element.closest('[hidden],[inert]')&&element.getClientRects().length>0&&getComputedStyle(element).visibility!=='hidden';
    const semanticEditors=Array.from(document.querySelectorAll('[role="combobox"][contenteditable="true"],[role="textbox"][contenteditable="true"]')).filter(visible);
    const editors=Array.from(new Set([...semanticEditors,...Array.from(document.querySelectorAll('[aria-label="Message input"]')).filter(visible)]));
    const stableModels=Array.from(document.querySelectorAll('[data-testid="model-selector-trigger"]')).filter(visible);
    const models=stableModels.length?stableModels:Array.from(document.querySelectorAll('button[role="combobox"][aria-haspopup],button[aria-label^="Select model"]')).filter(visible);
    const pairs=[];
    const ownsEditor=(element,editor)=>element.closest('[data-testid="agent-input-box"]')===editor.closest('[data-testid="agent-input-box"]');
    for(const model of models)for(const editor of editors){
      if(!ownsEditor(model,editor))continue;
      let row=model.parentElement,distance=1;
      // The toolbar branch and editable branch meet at their nearest common
      // composer ancestor. Action-button labels and generation state are irrelevant.
      while(row?.parentElement&&!row.parentElement.contains(editor)&&row.parentElement!==document.body&&row.parentElement!==document.documentElement){row=row.parentElement;distance++;}
      if(!row||row===document.body||row.contains(editor)||!row.parentElement?.contains(editor)||[document.body,document.documentElement].includes(row.parentElement))continue;
      for(let element=editor;element&&element!==row.parentElement;element=element.parentElement)distance++;
      let branch=model;while(branch.parentElement!==row)branch=branch.parentElement;
      const pair={editor,model,row,branch,box:editor.closest('[data-testid="agent-input-box"]'),distance,kind:'main'};
      if(composerLayout(pair))pairs.push(pair);
    }
    // Subagents have a static identity badge instead of a model selector.
    // Use only a bounded, stable host input box with a semantic send control;
    // never use the auxiliary pane's arbitrary comboboxes as an anchor.
    for(const editor of editors){
      const box=editor.closest('[data-testid="agent-input-box"]');
      if(!box||!visible(box))continue;
      const owned=e=>e.closest('[data-testid="agent-input-box"]')===box;
      const activeEditors=Array.from(box.querySelectorAll('[contenteditable="true"]')).filter(e=>owned(e)&&visible(e));
      if(!activeEditors.includes(editor)||activeEditors.length!==1)continue;
      if(Array.from(box.querySelectorAll('[data-testid="model-selector-trigger"]')).some(e=>owned(e)&&visible(e)))continue;
      const controls=Array.from(box.querySelectorAll('[data-testid="send-button"],[data-tooltip-id*="send-button"],[data-testid="stop-button"],[data-testid="cancel-button"],button[aria-label]'))
        .filter(e=>owned(e)&&visible(e)&&(e.hasAttribute('data-testid')&&/^(send|stop|cancel)-button$/.test(e.dataset.testid)||e.getAttribute('data-tooltip-id')?.includes('send-button')||/^(?:cancel|stop|取消|停止)(?:\b|\s|生成|任务|响应|$)/i.test(e.getAttribute('aria-label')||'')));
      for(const send of controls){
        let row=send.parentElement,distance=1;
        while(row?.parentElement&&row.parentElement!==box&&!row.parentElement.contains(editor)){row=row.parentElement;distance++;}
        if(!row||row.contains(editor)||!row.parentElement?.contains(editor)||!box.contains(row))continue;
        // The smallest static icon+text badge is structural evidence, even
        // without title/span. Icon-only controls and ambiguous badges fail closed.
        const interactive='button,a,input,select,[contenteditable="true"],[role="button"],[role="combobox"],[aria-haspopup]';
        const candidates=Array.from(row.querySelectorAll('*')).filter(e=>owned(e)&&visible(e)&&e.id!==ID&&!e.closest('#'+ID)&&e.querySelector('svg')&&badgeTextRects(e).length&&!e.contains(send)&&!send.contains(e)&&!e.matches(interactive)&&!e.closest(interactive)&&!e.querySelector(interactive));
        const anchors=candidates.filter(e=>!candidates.some(other=>other!==e&&e.contains(other)));
        if(anchors.length!==1)continue;
        const anchor=anchors[0];let branch=anchor;while(branch.parentElement!==row)branch=branch.parentElement;
        if(branch.contains(send))continue;
        for(let element=editor;element&&element!==row.parentElement;element=element.parentElement)distance++;
        const pair={editor,model:null,row,branch,anchor,box,distance,kind:'subagent'};
        if(composerLayout(pair)&&!pairs.some(p=>p.editor===editor&&p.row===row&&p.branch===branch))pairs.push(pair);
      }
    }
    pairs.sort((a,b)=>a.distance-b.distance);
    if(!pairs.length)return null;
    const focused=pairs.filter(pair=>pair.editor===document.activeElement||pair.editor.contains(document.activeElement));
    if(focused.length===1)return focused[0];
    const retained=pairs.filter(pair=>pair.branch===composer?.branch&&pair.editor===composer?.editor);
    if(retained.length===1)return retained[0];
    // Equally plausible visible composers must not place the strip arbitrarily.
    const closest=pairs.filter(pair=>pair.distance===pairs[0].distance);
    if(closest.length===1)return closest[0];
    return closest.find(pair=>pair.editor===document.activeElement)||closest.find(pair=>pair.branch===composer?.branch&&pair.editor===composer?.editor)||null;
  }
  function mount(){
    if(disposed)return;
    // A replaced instance's delayed preferences/observer callback must never
    // resurrect it. Also remove identifiable leftovers from older runtimes
    // before measuring the native toolbar or attaching this instance's host.
    for(const orphan of document.querySelectorAll('[id="'+ID+'"]')){
      if(orphan!==node&&['speed','cache','context'].every(name=>orphan.shadowRoot?.querySelector('.bar .chip[data-card="'+name+'"]')))orphan.remove();
    }
    // Account usage does not belong to a composer lifecycle. Keep its frame
    // during reflows and park the host if the app replaces the input subtree.
    // Normal discovery reattaches the strip after the user closes the modal.
    if(usageDashboard?.isOpen&&node){
      if(!node.isConnected||!node.getClientRects().length){node.dataset.layout='blocked';document.body.append(node);usageDashboard.restoreModal();}
      return;
    }
    const found=findComposer();
    if(!found){
      stopDensityMotion();densityFrame=null;densityProbe=null;composer=null;resizeObserver?.disconnect();
      if(node){
        hide();usageDashboard?.dispose();usageDashboard=null;updateMenu?.dispose();updateMenu=null;themeController?.dispose();themeController=null;
        node.remove();node=null;root=null;
        // A disposed dialog cannot be reused with its old strip/listeners.
        // Invalidate this mount's pending requests and rebuild on discovery.
        requestEpoch++;pending=false;refreshRequest=null;manualRequest=null;lastFetch=0;
      }
      return;
    }
    found.native=composer?.branch===found.branch&&composer?.anchor===found.anchor?composer.native:captureNative(found);
    if(found.kind==='ide'&&surface?.nativeReserve)found.native.reserve=surface.nativeReserve(found);
    composer=found;
    if(syncConversation())render();
    const {editor,model,row,branch}=found;
    if(node)node.dataset.scope=found.kind;
    if(node?.isConnected&&node.parentElement===row&&node.previousElementSibling===branch)return;
    if(node){stopDensityMotion();densityFrame=null;densityProbe=null;hide();row.insertBefore(node,branch.nextSibling);observeComposer();themeController?.dispose();themeController=theme.attach(node,{embedded:true});if(data?.theme)themeController.setHostTheme(data.theme);fit();position();return;}
    resizeObserver?.disconnect();node?.remove();node=document.createElement('div');node.id=ID;
    node.dataset.scope=found.kind;
    node.style.cssText='display:flex;align-items:center;flex:0 0 auto;width:100%;min-width:0;height:28px;padding:0 4px;margin:2px 0 4px 0;position:relative;box-sizing:border-box;';
    root=node.attachShadow({mode:'open'});
    setMarkup(root,`<style>${theme.shadowCss()}
      :host{color-scheme:var(--pulse-scheme);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;color:var(--pulse-foreground);font-size:11px}*{box-sizing:border-box}button,select{font:inherit}button{cursor:pointer}svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.2;stroke-linecap:round;stroke-linejoin:round;flex:none}button:focus-visible,select:focus-visible{outline:2px solid var(--pulse-accent);outline-offset:2px}
      .bar{display:flex;justify-content:flex-start;width:100%;align-items:center;gap:7px;min-height:28px;padding:2px 0}.chip{display:flex;align-items:center;gap:6px;color:var(--pulse-chip);background:none;border:0;border-radius:5px;padding:3px 6px;white-space:nowrap;line-height:18px}.chip:hover,.chip[aria-expanded=true]{background:var(--pulse-hover);color:var(--pulse-hover-text)}.chip strong{font-weight:500;font-variant-numeric:tabular-nums}.dim{color:var(--pulse-muted)}.countdown{font-size:10px;font-variant-numeric:tabular-nums}.dot{width:4px;height:4px;background:var(--pulse-dot);border-radius:50%;flex:none}.dot.live{background:var(--pulse-success)}.dot.stale{background:var(--pulse-warning)}.group{color:var(--pulse-muted);font-size:10px;margin-right:1px}.card{position:fixed;inset:auto;margin:0;z-index:2147483000;padding:13px 14px 11px;border-radius:13px;background:linear-gradient(145deg,var(--pulse-card),var(--pulse-card-end));box-shadow:0 8px 32px var(--pulse-shadow);border:1px solid var(--pulse-border);color:var(--pulse-foreground);font-size:12px}.card::backdrop{background:transparent;pointer-events:none}.card[hidden]{display:none}dl>[hidden]{display:none}.heading{display:flex;align-items:center;justify-content:space-between;padding-bottom:10px;margin-bottom:9px;border-bottom:1px solid var(--pulse-separator);font-weight:600}.heading span{display:flex;align-items:center;gap:7px}.tag{font-size:10px;font-weight:400;color:var(--pulse-muted)}dl{margin:0}dl div{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin:8px 0}dt{color:var(--pulse-label);font-size:11px}dd{margin:0;font-size:11px;font-variant-numeric:tabular-nums;text-align:right}.emphasis dd{font-weight:600;color:var(--pulse-emphasis)}.footnote{font-size:10px;color:var(--pulse-subtle);line-height:1.6;margin:10px 0 0}.balance{display:flex;align-items:baseline;gap:8px;margin:12px 0}.balance strong{font-size:27px;font-weight:550;letter-spacing:-.6px;font-variant-numeric:tabular-nums}.balance span{color:var(--pulse-muted);font-size:11px}.track{height:4px;border-radius:3px;background:var(--pulse-track);margin:12px 0 14px;overflow:hidden}.track i{height:100%;display:block;background:var(--pulse-accent);width:0}select{color:var(--pulse-control-text);background:var(--pulse-control);border:0;border-radius:4px;font-size:10px;padding:3px 5px;max-width:120px}.toolbar{display:flex;align-items:center;gap:7px}.refresh{color:var(--pulse-muted);border:0;background:transparent;padding:0 3px;font-size:14px}.reset{color:var(--pulse-emphasis)}.rounds,.group,.dot.live{display:none}.chip[hidden]{display:none}.toolbar{position:relative}.group-trigger{color:var(--pulse-control-text);background:var(--pulse-control);border:0;border-radius:5px;font-size:10px;padding:4px 7px;white-space:nowrap}.group-menu{position:absolute;top:calc(100% + 5px);right:22px;min-width:132px;padding:4px;background:var(--pulse-menu);border:1px solid var(--pulse-border);border-radius:7px;box-shadow:0 6px 20px var(--pulse-shadow);z-index:10}.group-menu[hidden]{display:none}.group-menu button{display:block;width:100%;padding:7px 9px;border:0;border-radius:4px;background:none;color:var(--pulse-foreground);text-align:left;white-space:nowrap}.group-menu button:hover,.group-menu button[aria-selected=true]{background:var(--pulse-selected)}.chip{padding:2px 4px;font-size:10px;gap:4px;min-width:0}.bar{gap:3px}.language-button{border:0;background:none;color:var(--pulse-muted);border-radius:4px;font-size:9px;padding:3px 4px;margin-left:auto;cursor:pointer;flex:none}.language-button:hover{color:var(--pulse-hover-text);background:var(--pulse-hover)}:host(.compact) .countdown{display:none}:host(.narrow) .cache-total{display:none}:host(.narrow) [data-card="cache"] .dim{display:none}:host(.narrow) .chip svg{display:none}:host(.narrow) .chip{padding:2px 3px;font-size:9px}:host(.narrow) .bar{gap:0}

      :host([data-layout=blocked]){opacity:0.9}.bar{overflow:clip;min-width:0;max-width:100%}
    :host(.native-no-room){flex:0 0 0px!important;width:0!important;max-width:0!important;margin:0!important}
    .density-stage{position:absolute;overflow:clip;pointer-events:none;user-select:none}.density-piece{pointer-events:none!important}
    .scope-note{margin:0 0 10px;color:var(--pulse-muted);font-size:10px}:host([data-scope=main]) .scope-note,:host([data-scope=ide]) .scope-note{display:none}
    .language-button[data-save-failed=true]{color:var(--pulse-warning);text-decoration:underline dotted}.context-ring{display:inline-block;flex:none;width:12px;height:12px;border-radius:50%;background:conic-gradient(var(--pulse-ring) var(--used-angle,0deg),var(--pulse-ring-track) 0);mask:radial-gradient(circle,transparent 43%,#000 47%)}:host(.narrow) .context-label{display:none}
    #rate-note{white-space:pre-line;font-size:11px;line-height:1.65}
    .footnote[hidden]{display:none}
    #transcript-details{margin-top:12px;border-top:1px solid var(--pulse-separator);padding-top:10px}#transcript-details summary{cursor:pointer;font-size:11px;color:var(--pulse-label)}#transcript-total{float:right;margin-left:8px;font-variant-numeric:tabular-nums;color:var(--pulse-foreground);font-size:10px}
    .bar{gap:6px}.chip{font-size:11px;gap:5px;padding:3px 5px}.context-card>strong{font-size:16px}.context-card>p{margin:8px 0}.quota-heading{margin-top:14px;padding-top:12px;border-top:1px solid var(--pulse-separator)}.quota-title{display:flex;align-items:center;gap:6px;font-size:11px}.quota-title>span:first-child{display:flex;align-items:center;gap:6px;margin-right:auto}.quota-title strong{font-variant-numeric:tabular-nums;font-size:13px}.quota-section+.quota-section{border-top:1px solid var(--pulse-separator);margin-top:12px;padding-top:12px}.quota-section .track{margin:8px 0}.quota-section .footnote{margin-top:6px}.quota-section dl div{margin:6px 0}.context-label{white-space:nowrap}
    :host(.icons-only) .bar{gap:2px}:host(.icons-only) .chip{flex:0 0 24px;width:24px;min-width:24px;height:24px;padding:0;gap:0;justify-content:center}:host(.icons-only) .chip>:not(svg):not(.context-ring){display:none}:host(.icons-only) .bar>.language-button,:host(.icons-only) .bar>.dot{display:none}:host(.icons-only) .chip svg{display:block}.card-language{display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding-top:8px;border-top:1px solid var(--pulse-separator);font-size:10px;color:var(--pulse-muted)}
    .refresh{display:inline-grid;place-items:center}.refresh[aria-busy=true]{color:var(--pulse-emphasis);cursor:wait}.refresh[aria-busy=true] svg{animation:pulse-refresh-spin 1s linear infinite;transform-origin:center}
    @keyframes pulse-refresh-spin{to{transform:rotate(360deg)}}
    @media(prefers-reduced-motion:reduce){.refresh[aria-busy=true] svg{animation:none;opacity:.65}}
    </style><div class="bar" data-i18n-aria="strip" aria-label="Dashboard statistics">
      <span class="dot" id="dot" title="Connecting"></span>
      <button class="chip" data-card="speed" data-i18n-aria="session" hidden aria-controls="speed-card" aria-expanded="false">${svg('speed')}<span class="rounds dim" id="rounds"></span><strong id="tps">—</strong><span>tok/s</span></button>
      <button class="chip" data-card="cache" data-i18n-aria="cacheTitle" hidden aria-controls="cache-card" aria-expanded="false">${svg('cache')}<span class="cache-total" id="cache-total">— tok</span><span class="dim">·</span><span data-i18n="cache">Cache hit</span><strong id="cache-rate">—</strong></button>
      <button class="chip" data-card="context" data-i18n-aria="context" hidden aria-controls="context-card" aria-expanded="false"><span class="context-ring" id="context-ring" aria-hidden="true"></span><span class="context-label" data-i18n="contextShort">Ctx</span><strong id="context-percent">—</strong></button>
    </div><section class="card" id="speed-card" role="region" data-i18n-aria="session" aria-label="Session statistics" hidden>
      <div class="heading"><span>${svg('speed')}<span data-i18n="session">Session statistics</span></span><span class="tag" id="samples">—</span></div>
      <dl>${[['modelTime','model-time'],['toolTime','tool-time'],['ttft','ttft'],['sessionTps','session-rate'],['latest','latest-rate'],['tokens','tokens']].map(([key,id])=>`<div><dt data-i18n="${key}">${t(key)}</dt><dd id="${id}">—</dd></div>`).join('')}</dl><p class="footnote" id="rate-note">${t('responseBasis')}</p>
    </section><section class="card" id="cache-card" role="region" data-i18n-aria="cacheTitle" aria-label="Token cache" hidden>
      <div class="heading"><span>${svg('cache')}<span data-i18n="cacheTitle">Token cache</span></span><span class="tag" id="cache-coverage">—</span></div>
      <dl>${[['cacheRate','cache-detail-rate'],['cacheMiss','cache-miss'],['cacheRead','cache-read'],['cacheOutput','cache-output'],['cacheWrite','cache-write']].map(([key,id])=>`<div ${id==='cache-write'?'id="cache-write-row" hidden':''}><dt data-i18n="${key}">${t(key)}</dt><dd id="${id}">—</dd></div>`).join('')}<div id="task-own-row" hidden><dt data-i18n="taskOwn">${t('taskOwn')}</dt><dd id="task-own">—</dd></div><div id="task-subagents-row" hidden><dt id="task-subagents-label"></dt><dd id="task-subagents">—</dd></div></dl><p class="footnote" id="cache-note" hidden></p>
    </section><section class="card context-card" id="context-card" role="region" data-i18n-aria="context" hidden>
      <div class="heading"><span>${svg('context')}<span data-i18n="context">Context window</span></span></div>
      <strong id="context-summary">—</strong><p id="context-tokens">—</p>
      <div class="track" role="progressbar" data-i18n-aria="context" id="context-track"><i id="context-fill"></i></div>
      <dl><div><dt data-i18n="contextModel">Sampled model</dt><dd id="context-model">—</dd></div></dl>
      <div class="heading quota-heading"><span data-i18n="group">Quota group</span><div class="toolbar"><button class="group-trigger" data-i18n-aria="group" aria-haspopup="listbox" aria-expanded="false">Quota ▾</button><div class="group-menu" role="listbox" data-i18n-aria="selectGroup" hidden></div><button class="refresh" data-i18n-aria="refresh" aria-label="Refresh quota" title="Refresh quota"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M12.8 6a5.1 5.1 0 1 0 .1 4M12.8 2.5V6H9.2"/></svg></button></div></div>
      <div class="quota-details">${['five','week'].map(name=>`<section class="quota-section" data-i18n-aria="${name}" aria-label="${t(name)}"><div class="quota-title"><span>${svg(name)}<span data-i18n="${name}">${t(name)}</span></span><strong id="${name}-balance">—</strong><span class="dim" data-i18n="remaining">remaining</span></div><div class="track" role="progressbar" data-i18n-aria="${name}" id="${name}-track"><i id="${name}-fill"></i></div><dl><div><dt data-i18n="resetIn">Resets in</dt><dd class="reset" id="${name}-countdown">—</dd></div><div><dt data-i18n="resetTime">Reset time (UTC+8)</dt><dd id="${name}-reset">—</dd></div></dl><p class="footnote" id="${name}-note" hidden></p></section>`).join('')}</div>
    </section>`);
    row.insertBefore(node,branch.nextSibling);
    for(const card of root.querySelectorAll('.card')){const note=document.createElement('p');note.className='scope-note';note.dataset.i18n='subagentStats';card.querySelector('.heading').after(note);}
    const languageRow=document.createElement('div');languageRow.className='card-language';
    setMarkup(languageRow,'<span data-i18n="language"></span><div class="language-options" role="group" data-i18n-aria="language"><button type="button" class="language-button" id="card-language-en" data-language-choice="en">English</button><button type="button" class="language-button" id="card-language-zh" data-language-choice="zh-CN">简体中文</button><button type="button" class="language-button" id="card-language-zh-tw" data-language-choice="zh-TW">繁體中文</button></div>');
    $('context-card').append(languageRow);
    if(window.__agPulseUpdateFactory&&window.agPulseHost.updatePlugin)updateMenu=window.__agPulseUpdateFactory({root,row:languageRow,language,setMarkup,request:input=>window.agPulseHost.updatePlugin(input),onOpen:hide});
    const saveNote=document.createElement('p');saveNote.className='footnote';saveNote.id='language-save-note';languageRow.after(saveNote);
    const guide=document.createElement('section');guide.className='language-guide';guide.id='language-guide';guide.hidden=true;guide.setAttribute('role','region');guide.setAttribute('aria-label','Language / 語言 / 语言');
    setMarkup(guide,'<div class="guide-heading"><strong>Language <span>/ 语言</span></strong><button type="button" id="guide-close" aria-label="Dismiss language tip / 关闭语言提示" title="Dismiss / 关闭">×</button></div><button type="button" id="guide-open"><span><span>Switch in context details</span><span lang="zh-CN">在上下文详情中切换语言</span></span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h9M8 4l4 4-4 4"/></svg></button><p class="footnote" id="guide-save-note"></p>');
    root.append(guide);
    const guideStyle=document.createElement('style');guideStyle.textContent=`
      .card-language{margin:10px 0 0;padding:8px 0 0;border-top:1px solid var(--pulse-separator);border-bottom:0;gap:8px;font-size:10px}
      .language-options{display:flex;gap:2px;padding:2px;border-radius:6px;background:var(--pulse-control);flex:none}
      .language-options .language-button{font-size:10px;padding:3px 6px;margin:0;border-radius:4px;color:var(--pulse-muted);line-height:16px;transition:background-color 140ms ease,color 140ms ease,transform 120ms ease}
      .language-options .language-button[aria-pressed=true]{color:var(--pulse-foreground);background:var(--pulse-hover);box-shadow:0 1px 2px var(--pulse-shadow)}
      .language-options .language-button:active{transform:scale(.97)}
      .language-guide{position:fixed;inset:auto;margin:0;padding:10px 12px;border:1px solid var(--pulse-border);border-radius:10px;background:var(--pulse-card);color:var(--pulse-foreground);box-shadow:0 4px 16px var(--pulse-shadow);font-size:11px;z-index:2147483000;overflow:visible}
      .language-guide[hidden]{display:none}.language-guide::backdrop{background:transparent;pointer-events:none}
      .language-guide::after{content:'';position:absolute;left:calc(var(--guide-anchor) - 4px);width:7px;height:7px;transform:rotate(45deg);background:var(--pulse-card);pointer-events:none}
      .language-guide[data-side=above]::after{bottom:-4px;border-right:1px solid var(--pulse-border);border-bottom:1px solid var(--pulse-border)}
      .language-guide[data-side=below]::after{top:-4px;border-left:1px solid var(--pulse-border);border-top:1px solid var(--pulse-border)}
      .guide-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:18px}
      .guide-heading strong{font-size:11px;font-weight:600}.guide-heading strong span{font-weight:400;color:var(--pulse-muted)}
      .language-guide button{border:0;background:transparent;color:var(--pulse-muted);border-radius:4px;cursor:pointer;font:inherit;transition:color 140ms ease,background-color 140ms ease,transform 120ms ease}
      .language-guide button:hover{background:var(--pulse-hover);color:var(--pulse-foreground)}.language-guide button:active{transform:scale(.98)}
      #guide-close{font-size:15px;line-height:18px;width:20px;height:20px;margin:-3px -4px -3px 0;padding:0}
      #guide-open{display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:left;width:calc(100% + 8px);margin:5px -4px -3px;padding:4px;line-height:16px}
      #guide-open>span{display:grid;gap:1px}#guide-open span[lang]{font-size:10px;color:var(--pulse-muted)}#guide-open svg{width:14px;height:14px;flex:none}
      #guide-save-note:empty,#language-save-note:empty{display:none}#guide-save-note,#language-save-note{color:var(--pulse-warning)}
    `;root.append(guideStyle);
    $('guide-close').addEventListener('click',()=>void dismissGuide());
    $('guide-open').addEventListener('click',()=>{guideOpened=true;show('context');const btn=$(language.language==='zh-TW'?'card-language-zh-tw':'card-language-zh');btn.scrollIntoView({block:'nearest'});btn.focus({preventScroll:true});});
    // Escape ancestor stacking/paint contexts; ordinary z-index cannot do this.
    if(typeof HTMLElement.prototype.showPopover==='function')for(const card of root.querySelectorAll('.card'))card.setAttribute('popover','manual');
    if(typeof guide.showPopover==='function')guide.setAttribute('popover','manual');
    themeController=theme.attach(node,{embedded:true});
    report('mounted',{editorFound:true,composerFound:true});
    observeComposer();
    for(const chip of root.querySelectorAll('[data-card]')){
      chip.addEventListener('pointerenter',()=>hoverChip(chip.dataset.card));chip.addEventListener('pointerleave',leaveChip);chip.addEventListener('focus',()=>{if(chip.matches(':focus-visible'))show(chip.dataset.card);});chip.addEventListener('click',()=>show(chip.dataset.card));
    }
    for(const card of root.querySelectorAll('.card')){
      card.addEventListener('pointerenter',()=>clearTimeout(hoverTimer));card.addEventListener('pointerleave',scheduleHide);
    }
    // A host composer may focus its editor on bubbled clicks. Keep plugin
    // controls' mouse actions inside the shadow root while retaining their
    // default focus/click behavior and document-level outside-click dismissal.
    for(const type of ['pointerdown','mousedown','click'])root.addEventListener(type,event=>event.stopPropagation());
    node.addEventListener('pointerenter',()=>clearTimeout(hoverTimer));node.addEventListener('pointerleave',scheduleHide);
    root.addEventListener('focusout',()=>setTimeout(()=>{if(!cardEngaged())hide();},0));
    for(const button of root.querySelectorAll('.group-trigger'))button.addEventListener('click',()=>{
      const menu=button.parentElement.querySelector('.group-menu');const opening=menu.hidden;closeGroup();if(opening){groupMenu=menu;menu.hidden=false;button.setAttribute('aria-expanded','true');}
    });
    for(const button of root.querySelectorAll('.refresh'))button.addEventListener('click',refreshManually);
    for(const button of root.querySelectorAll('[data-language-choice]'))button.addEventListener('click',()=>{closeGroup();void preferences.choose(button.dataset.languageChoice);});
    if(window.__agPulseUsageFactory){
      const section=document.createElement('div');section.id='usage-entry';section.hidden=true;
      setMarkup(section,'<dl class="usage-summary"><div><dt id="usage-today-label"></dt><dd><strong id="usage-today"></strong><span class="usage-unit">Token</span></dd></div><div><dt id="usage-month-label"></dt><dd><strong id="usage-month"></strong><span class="usage-unit">Token</span></dd></div></dl><button type="button" id="open-usage"><span id="usage-open-label"></span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4"/></svg></button>');$('cache-card').append(section);
      const css=document.createElement('style');css.textContent='#usage-entry{border-top:1px solid var(--pulse-separator);padding-top:7px;margin-top:12px}#usage-entry[hidden]{display:none}#open-usage{width:100%;display:flex;justify-content:space-between;padding:8px 10px;margin-top:9px;border:1px solid var(--pulse-border);border-radius:7px;background:var(--pulse-control);color:var(--pulse-foreground);font:inherit;transition:background 140ms ease,transform 120ms ease}#open-usage:hover{background:var(--pulse-hover)}#open-usage:active{transform:scale(.98)}';root.append(css);
      css.textContent+=`
        #usage-entry{padding-top:13px;margin-top:14px}.usage-summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;padding-bottom:13px;border-bottom:1px solid var(--pulse-separator)}
        .usage-summary>div{display:block;min-width:0;margin:0}.usage-summary dt{font-size:10px;line-height:16px;color:var(--pulse-muted);margin:0 0 5px}.usage-summary dd{display:flex;align-items:baseline;justify-content:flex-start;gap:5px;margin:0;white-space:nowrap;text-align:left;line-height:24px}
        .usage-summary strong{font-size:20px;font-weight:550;letter-spacing:-.5px;color:var(--pulse-foreground);font-variant-numeric:tabular-nums}.usage-unit{font-size:9px;letter-spacing:0;color:var(--pulse-muted)}
        #open-usage{align-items:center;min-height:34px;gap:12px;width:calc(100% + 12px);margin:5px -6px -3px;padding:7px 6px;border:0;border-radius:6px;background:transparent;color:var(--pulse-label);font-size:11px;text-align:left;line-height:20px}#open-usage:hover{background:var(--pulse-hover);color:var(--pulse-foreground)}#open-usage svg{width:14px;height:14px;color:var(--pulse-muted);flex:none}
      `;
      usageDashboard=window.__agPulseUsageFactory({root,language,setMarkup,hostLabel:surface?.usageHostLabel||'Antigravity',guideDismissed:usageGuideDismissed,onDismissGuide:async()=>{const saved=await window.agPulseHost.setPreferences({usageGuideDismissed:true});if(saved?.usageGuideDismissed!==true)throw Error('Usage guide could not be saved');syncGuide(saved);},onLanguage:next=>preferences.choose(next),onRefresh:()=>refreshManually()});
      $('open-usage').addEventListener('click',()=>{const trigger=root.querySelector('[data-card=cache]');hide();usageDashboard.open(data?.usage,trigger);});
    }
    localize();
    render();refresh();
  }
  function render(){
    if(!root||!data)return;
    syncConversation();
    if(usageDashboard){
      const available=Boolean(data.usage);hidden($('usage-entry'),!available);
      text('usage-today',compact(data.usage?.todayTokens));text('usage-month',compact(data.usage?.monthTokens));usageDashboard.update(data.usage);
    }
    if(groupMenu)return;
    const groups=data.groups||[],model=composer?.model?.getAttribute('aria-label')||composer?.model?.textContent||data.speed?.model||'';
    group=groups.find(g=>g.id===chosen)||groups.find(g=>/gemini/i.test(model)?/gemini/i.test(g.id):/claude|gpt/i.test(model)?/3p|claude|gpt/i.test(g.id):false)||groups[0];
    for(const button of root.querySelectorAll('.group-trigger')){
      if(button.textContent!==`${label(group)} ▾`)button.textContent=`${label(group)} ▾`;
      const menu=button.parentElement.querySelector('.group-menu'),signature=groups.map(g=>g.id).join('|');
      if(menu.dataset.signature!==signature){menu.replaceChildren(...groups.map(g=>{const option=document.createElement('button');option.type='button';option.setAttribute('role','option');option.textContent=label(g);option.dataset.group=g.id;option.addEventListener('click',()=>{chosen=g.id;localSet('ag-pulse-group',chosen);closeGroup();render();menu.parentElement.querySelector('.group-trigger')?.focus({preventScroll:true});});return option;}));menu.dataset.signature=signature;}
      for(const option of menu.children)attribute(option,'aria-selected',option.dataset.group===group?.id);
    }
    const speed=data.speed;
    hidden(root.querySelector('[data-card="speed"]'),!lastConversation&&!surface?.showEmpty);
    hidden(root.querySelector('[data-card="cache"]'),!lastConversation&&!surface?.showEmpty&&!data.usage);
    const context=speed?.context, hasCapacity=typeof context?.usedFraction==='number';
    hidden(root.querySelector('[data-card="context"]'),false);
    const empty=surface?.conversationState?.(composer).status==='new'&&!lastConversation&&data.connection==='live';
    text('context-percent',hasCapacity?`${Math.round(context.usedFraction*100)}%`:'—');
    style($('context-ring'),'--used-angle',`${hasCapacity?Math.min(1,context.usedFraction)*360:0}deg`);
    text('context-summary',hasCapacity?t('contextUsed',{used:Math.round(context.usedFraction*100),remaining:Math.round(context.remainingFraction*100)}):t(empty?'waitingRequest':'contextUnknown'));
    text('context-tokens',context?t('contextTokens',{used:compact(context.usedTokens),max:context.maxTokens===null?'—':compact(context.maxTokens)}):'—');
    text('context-model',context?.model||'—');
    style($('context-fill'),'width',hasCapacity?`${Math.min(1,context.usedFraction)*100}%`:'0%');
    style($('context-fill'),'background',hasCapacity&&context.usedFraction>=.9?'var(--pulse-danger)':'');
    attribute($('context-track'),'aria-valuenow',hasCapacity?Math.min(100,context.usedFraction*100):null);attribute($('context-track'),'aria-valuemin','0');attribute($('context-track'),'aria-valuemax','100');
    text('tps',rate(speed?.tps));text('rounds',speed?t('rounds',{rounds:speed.rounds,steps:speed.steps}):'');
    text('samples',speed?t('sample',{rounds:speed.rounds,steps:speed.steps,requests:speed.measuredRequests}):t('waitingRequest'));text('model-time',seconds(speed?.modelSeconds));text('tool-time',seconds(speed?.toolSeconds));text('ttft',seconds(speed?.ttftSeconds));text('session-rate',`${rate(speed?.tps)} tok/s`);text('latest-rate',`${rate(speed?.latestTps)} tok/s`);text('tokens',speed?`${count(speed.counts.responseOutput)} / ${count(speed.counts.thinkingOutput)} tok`:'—');
    if(speed?.latestRateStatus==='unreliable')text('latest-rate',t('timingUnreliable'));
    if(speed?.latestRateStatus==='legacy'){text('latest-rate',t('ratePending'));text('session-rate',t('ratePending'));}
    const savedNote=speed?.restoredFromHistory?' '+t('savedStats',{time:speed.savedAt?language.resetDate(speed.savedAt):'—'}):'';
    const saveWarning=data.persistenceError?' '+t('saveFailed'):'';
    text('rate-note',[language.errorMessage(data.error||data.sessionError),language.rateNote(speed)].filter(Boolean).join(' ')+savedNote+saveWarning);
    const taskUsage=Number.isSafeInteger(speed?.taskUsage?.subagents)&&speed.taskUsage.subagents>0?speed.taskUsage:null;
    const usage=taskUsage||speed,cache=usage?.cache;
    text('cache-rate',pct(cache?.hitRate));text('cache-detail-rate',pct(cache?.hitRate));
    const tokens=usage?.tokens || cache;
    // Keep coverage in the data model; the compact card shows readable counters.
    const hasTotal=tokens?.measuredRequests&&Number.isSafeInteger(tokens.totalTokens)&&tokens.totalTokens>=0;
    text('cache-total',hasTotal?`${compact(tokens.totalTokens)} tok`:'— tok');
    text('cache-coverage',hasTotal?`${count(tokens.totalTokens)} tok`:'— tok');
    const inputCoverage={uncachedTokens:'uncachedRequests',cachedTokens:'cachedRequests',cacheWriteTokens:'cacheWriteRequests'};
    for(const [field,id]of[['cachedTokens','cache-read'],['uncachedTokens','cache-miss'],['cacheWriteTokens','cache-write'],['outputTokens','cache-output']]) {
      const available=field==='outputTokens'?(tokens?.outputAvailable??(tokens?.outputRequests??tokens?.measuredRequests)):(tokens?.[inputCoverage[field]]??tokens?.inputRequests??tokens?.measuredRequests);
      const known=Number.isSafeInteger(tokens?.[field])&&tokens[field]>=0;
      text(id,available&&known?`${count(tokens[field])} tok`:'—');
    }
    hidden($('cache-write-row'),!(tokens?.cacheWriteTokens>0));
    hidden($('task-own-row'),!taskUsage);hidden($('task-subagents-row'),!taskUsage);
    text('task-subagents-label',taskUsage?t('taskSubagents',{n:count(taskUsage.subagents)}):'');
    for(const [field,id]of[['ownTokens','task-own'],['subagentTokens','task-subagents']]){
      const value=taskUsage?.[field],known=field!=='subagentTokens'||taskUsage?.loadedSubagents>0;
      text(id,known&&Number.isSafeInteger(value)&&value>=0?`${count(value)} tok`:'—');
    }
    const taskNote=taskUsage?.state==='loading'?t('taskLoading'):taskUsage?.state==='partial'?t('taskPartial'):'';
    text('cache-note',taskNote);hidden($('cache-note'),!taskNote);
    for(const [window,name]of[['5h','five'],['weekly','week']]){
      const b=group?.windows?.[window];text(name,pct(b?.remaining));text(`${name}-balance`,pct(b?.remaining));text(`${name}-reset`,date(b?.resetAt));
      style($(`${name}-fill`),'width',typeof b?.remaining==='number'?`${b.remaining*100}%`:'0%');style($(`${name}-fill`),'background',b?.remaining<.05?'var(--pulse-danger)':b?.remaining<.2?'var(--pulse-warning)':'');
      attribute($(`${name}-track`),'aria-valuenow',typeof b?.remaining==='number'?b.remaining*100:null);attribute($(`${name}-track`),'aria-valuemin','0');attribute($(`${name}-track`),'aria-valuemax','100');
      text(`${name}-note`,(composer?.kind==='subagent'?t('accountQuota')+' ':'')+(language.errorMessage(data.error)||(b?.disabled?t('disabledQuota'):!b?.available?t('noQuota'):t('sharedQuota')+' '+t('updated',{time:data.quotaUpdatedAt?new Date(data.quotaUpdatedAt).toLocaleTimeString(language.language,{hour12:false}):'—'}))));
    }
    attribute($('dot'),'class',`dot ${data.connection}`);attribute($('dot'),'title',t(data.connection==='live'?'live':data.connection==='stale'?'stale':'offline'));tick();fit();position();
  }
  function tick(){
    if(!root)return;
    for(const [window,name]of[['5h','five'],['weekly','week']]){const b=group?.windows?.[window];text(`${name}-timer`,timer(b?.resetAt,true));text(`${name}-countdown`,timer(b?.resetAt));if(b?.resetAt&&Date.parse(b.resetAt)<=Date.now()&&Date.now()-lastExpiredRefresh>30000){lastExpiredRefresh=Date.now();refresh(true);}}
  }
  function refreshBusy(busy){
    for(const button of root?.querySelectorAll('.refresh')||[]){
      button.setAttribute('aria-busy',String(busy));button.setAttribute('aria-disabled',String(busy));
      button.dataset.i18nAria=busy?'refreshing':'refresh';button.title=t(button.dataset.i18nAria);button.setAttribute('aria-label',button.title);
    }
  }
  function refreshManually(){
    if(manualRequest)return manualRequest.promise;
    closeGroup();refreshBusy(true);const started=performance.now();
    const epoch=requestEpoch,request={};manualRequest=request;
    request.promise=(async()=>{
      try{if(pending)await refreshRequest;if(!disposed&&epoch===requestEpoch)await refresh(true);}
      finally{
        // A fast cached response still needs visible press feedback. This does
        // not delay data updates; only the indicator has a 250ms minimum.
        const remaining=250-(performance.now()-started);
        if(remaining>0)await new Promise(resolve=>setTimeout(resolve,remaining));
        if(manualRequest===request){refreshBusy(false);manualRequest=null;}
      }
    })();
    return request.promise;
  }
  function refresh(force=false){
    if(disposed)return;
    if(syncConversation())render();
    if(pending)return refreshRequest;
    if(!node?.isConnected)return;
    const conversation=conversationId();
    const epoch=requestEpoch;
    const current=()=>!disposed&&epoch===requestEpoch&&conversation===conversationId()&&conversation===lastConversation&&node?.isConnected;
    pending=true;lastFetch=Date.now();
    refreshRequest=(async()=>{
      try{const result=await window.agPulseHost.getMetrics({conversationId:conversation,force});if(!current())return;node.style.visibility=result.enabled===false?'hidden':'';if(result.enabled===false){hide();return;}if(!conversation||result.speed&&result.speed.conversationId!==conversation)result.speed=null;data=result;if(result.preferences){syncGuide(result.preferences);preferences.sync(result.preferences);guideReady=!preferences.error;}if(Object.hasOwn(result,'theme'))themeController?.setHostTheme(result.theme);render();}
      catch{if(current()&&data){data.connection='stale';data.error=t('reconnecting');render();}}
      finally{if(epoch===requestEpoch){pending=false;refreshRequest=null;}}
    })();
    return refreshRequest;
  }
  const observer=new MutationObserver(records=>{if(records.some(record=>record.target!==node&&!node?.contains(record.target)))scheduleLayout();});observer.observe(document.documentElement,{childList:true,subtree:true,attributes:true,attributeFilter:['style','class','hidden','inert','data-cascade-id','data-testid','data-tooltip-id','aria-label','role','contenteditable']});
  const onKey=e=>{if(e.key==='Escape')hide();}, onPointer=e=>{if(node&&!e.composedPath().includes(node))hide();};
  document.addEventListener('keydown',onKey);document.addEventListener('pointerdown',onPointer);
  window.addEventListener('resize',scheduleLayout);document.addEventListener('scroll',scheduleLayout,true);
  densityMedia.addEventListener('change',stopDensityMotion);
  const timerId=setInterval(()=>{mount();fit();tick();position();if(conversationId()!==lastConversation||Date.now()-lastFetch>(document.hidden?10000:2200))refresh();},1000);
  window.__agPulseDispose=()=>{
    disposed=true;requestEpoch++;pending=false;refreshRequest=null;stopDensityMotion();densityFrame=null;densityProbe=null;
    clearInterval(timerId);clearTimeout(hoverTimer);clearTimeout(openTimer);if(layoutFrame!==null)cancelAnimationFrame(layoutFrame);observer.disconnect();resizeObserver?.disconnect();themeController?.dispose();preferences.dispose();hide();usageDashboard?.dispose();updateMenu?.dispose();node?.remove();
    document.removeEventListener('keydown',onKey);document.removeEventListener('pointerdown',onPointer);
    document.removeEventListener('scroll',scheduleLayout,true);window.removeEventListener('resize',scheduleLayout);
    densityMedia.removeEventListener('change',stopDensityMotion);
    document.removeEventListener('DOMContentLoaded',mount);node=null;root=null;composer=null;
    window.__agPulseInlineInstalled=false;delete window.__agPulseDispose;
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
};
installAgPulseInlineWidget();


})();
