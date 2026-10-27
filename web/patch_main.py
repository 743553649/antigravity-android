#!/usr/bin/env python3
"""
web/patch_main.py - Patch web/main.js to:
1. Unlock native Custom Models in input selector (remove GoogleInternal locks).
2. Make Custom Model 'Edit' button always visible on mobile touchscreens (remove opacity-0).
3. Upgrade the Custom Model configuration modal (Gzb) with:
   - Fix for React useCallback stale closure (using both ref and full dependency array).
   - Direct persistence to window.__agCustomModelsStore & native .gemini/custom_models.json.
   - Saved models quick-select & delete chips at top of modal.
   - Single unified Model ID input + quick model chips.
   - One-tap API Base URL provider presets (AI Ping, DeepSeek, SiliconFlow, DashScope, OpenRouter) + live endpoint preview.
   - API Key visibility toggle (Show/Hide) + Clear button.
   - One-tap '⚡ 测试连接' (Test Connection) button with instant HTTP verification.
4. Add Desktop Mode toggle in Appearance settings.
"""

import sys
import os
import re

def patch_main(file_path):
    if not os.path.isfile(file_path):
        print(f"[web-patch] file not found: {file_path}", file=sys.stderr)
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # If already patched with v2 modal, shared storage, resume sync, and i18n, skip
    if "agTestConn" in content and "agLocalModels" in content and "agSd" in content and "agTrajectoriesRegistry" in content and "agI18nComplete" in content:
        print("[web-patch] main.js already patched with all customizations.")
        return True

    # 1. Unlock custom models gates in Ycc
    custom_model_gate = 'r=k.osName==="linux"&&k.isGoogleInternal;\nk=k.isGoogleInternal;'
    if custom_model_gate in content:
        content = content.replace(custom_model_gate, 'r=!0;\nk=!0;')
        print("[web-patch] Unlocked native Custom Models selector (Ycc)")

    # 2. Wire up customModelsFeature in workbench
    wire_custom_models = 'fa.customModelsFeature=N.features.customModelsFeature;'
    if wire_custom_models in content:
        content = content.replace(wire_custom_models, 'fa.customModelsFeature=x;')
        print("[web-patch] Wired fa.customModelsFeature to workbench provider")

    # 3. Unlock chat input header props
    chat_input_gate = 'supportsCustomModels:h,showCustomModelHeader:O'
    if chat_input_gate in content:
        content = content.replace(chat_input_gate, 'supportsCustomModels:!0,showCustomModelHeader:!0')
        print("[web-patch] Unlocked chat input Custom Models header & Add button")

    # 3b. Make Edit Model button in dropdown (RXb) always visible on mobile touchscreens
    old_edit_btn = 'className:"absolute right-1 top-1/2 -translate-y-1/2 flex items-center justify-center rounded p-1 opacity-0 transition-opacity hover:bg-secondary group-hover:opacity-100"'
    new_edit_btn = 'className:"absolute right-1 top-1/2 -translate-y-1/2 flex items-center justify-center rounded p-1 opacity-80 transition-opacity hover:bg-secondary hover:opacity-100"'
    if old_edit_btn in content:
        content = content.replace(old_edit_btn, new_edit_btn, 1)
        print("[web-patch] Made Edit Model button visible on mobile touchscreens (RXb)")

    # 3c. Merge local custom models into izc.customModelsProvider so SidePanel (jdc/Ycc) also sees them
    old_izc_cm = 'this.customModelsProvider=zi(this.rootProvider,b=>({customModels:b.appState?.customModelsConfig?.customModels??{}}));'
    new_izc_cm = (
        'this.customModelsProvider=zi(this.rootProvider,b=>{var cm={...(b.appState?.customModelsConfig?.customModels||{})};'
        'try{var lm=window.__agCustomModelsStore?window.__agCustomModelsStore.getModels():{};for(var k in lm){if(lm[k]?.modelInfo)cm[k]=lm[k].modelInfo}}catch(_){}'
        'return{customModels:cm}});'
    )
    if old_izc_cm in content:
        content = content.replace(old_izc_cm, new_izc_cm, 1)
        print("[web-patch] Patched izc.customModelsProvider to merge local custom models")

    # 4. Integrate Local Storage persistence + event listener into cCb Provider
    old_ccb = 'l=l?.customModelsProvider;var m=Pj(l),n=!!l,q=(0,A.useMemo)(()=>({customModels:m?.customModels??bCb}),[m]);return A.createElement(JX.Provider,{value:{customModelsState:q,\npushCustomModelsUpdate:l?l.pushUpdate:aCb'
    new_ccb = (
        'l=l?.customModelsProvider;var [agLocalModels,setAgLocalModels]=(0,A.useState)(()=>{try{return window.__agCustomModelsStore?window.__agCustomModelsStore.getModels():{}}catch(_){return {}}});'
        '(0,A.useEffect)(()=>{var h=()=>{try{setAgLocalModels({...(window.__agCustomModelsStore?window.__agCustomModelsStore.getModels():{})})}catch(_){}};'
        'window.addEventListener("ag-custom-models-changed",h);return()=>window.removeEventListener("ag-custom-models-changed",h)},[]);'
        'var m=Pj(l),n=!0,q=(0,A.useMemo)(()=>{var res={...(m?.customModels||{})};for(var k in agLocalModels){if(agLocalModels[k]?.modelInfo)res[k]=agLocalModels[k].modelInfo;}return {customModels:res}},[m,agLocalModels]);'
        'var agPushUpdate=(0,A.useCallback)(act=>{'
        'try{if(act.type==="addCustomModel"||act.type==="editCustomModel"){window.__agCustomModelsStore&&window.__agCustomModelsStore.addModel(act.label,act.modelInfo,act.apiKey,act.baseUrl,act.oldLabel);setAgLocalModels({...(window.__agCustomModelsStore.getModels())});}'
        'else if(act.type==="removeCustomModel"){window.__agCustomModelsStore&&window.__agCustomModelsStore.removeModel(act.label);setAgLocalModels({...(window.__agCustomModelsStore.getModels())});}'
        '}catch(e){console.error("agPushUpdate err",e);}'
        'if(l&&typeof l.pushUpdate==="function"){try{l.pushUpdate(act)}catch(_){}}'
        '},[l]);'
        'return A.createElement(JX.Provider,{value:{customModelsState:q,\npushCustomModelsUpdate:agPushUpdate'
    )
    if old_ccb in content:
        content = content.replace(old_ccb, new_ccb, 1)
        print("[web-patch] Integrated reactive persistent storage into cCb provider")

    # 5. Replace Gzb Custom Model Modal with upgraded UX & zero stale-closure bug
    idx_gzb_start = content.find("var Gzb=({isOpen:a,operation:b,onClose:c,modelName:e,customModelsState:f,pushCustomModelsUpdate:g,setSelectedModelConfig:h})=>")
    idx_gzb_end = content.find(";var Hzb=", idx_gzb_start) if idx_gzb_start != -1 else -1

    if idx_gzb_start != -1 and idx_gzb_end != -1:
        new_gzb = (
            'var Gzb=({isOpen:a,operation:b,onClose:c,modelName:e,customModelsState:f,pushCustomModelsUpdate:g,setSelectedModelConfig:h})=>{'
            'var [k,l]=(0,A.useState)(""),[m,n]=(0,A.useState)(""),[q,r]=(0,A.useState)("128000"),'
            '[agApiKey,setAgApiKey]=(0,A.useState)(""),[agBaseUrl,setAgBaseUrl]=(0,A.useState)("https://aiping.cn/api/v1"),'
            '[showAgKey,setShowAgKey]=(0,A.useState)(!1),[agTestStatus,setAgTestStatus]=(0,A.useState)(""),[agTesting,setAgTesting]=(0,A.useState)(!1),'
            '[agEditTarget,setAgEditTarget]=(0,A.useState)(void 0),'
            '[agSavedMap,setAgSavedMap]=(0,A.useState)(()=>{try{return window.__agCustomModelsStore?window.__agCustomModelsStore.getModels():{}}catch(_){return{}}}),'
            '[t,u]=(0,A.useState)(!0),[v,w]=(0,A.useState)(!0),[x,y]=(0,A.useState)(!0),'
            '{logEvent:B}=aA(),C=(0,A.useId)(),E=(0,A.useId)();'
            'var agFormRef=(0,A.useRef)({});'
            'agFormRef.current={k,m,q,agApiKey,agBaseUrl,t,v,x,b,e:agEditTarget||e};'
            'var loadSingleModel=(0,A.useCallback)(targetLabel=>{'
            'try{'
            'var allSaved=window.__agCustomModelsStore?window.__agCustomModelsStore.getModels():{};'
            'setAgSavedMap({...allSaved});'
            'var item=allSaved[targetLabel];'
            'var info=item?.modelInfo||f?.customModels?.[targetLabel];'
            'var cleanId=info?.chatModelName||targetLabel||"";'
            'l(cleanId);n(cleanId);'
            'r(String(info?.maxTokens||128000));'
            'u(info?.modelFeatures?.supportsImages??!0);'
            'w(info?.modelFeatures?.supportsToolCalls??!0);'
            'y(info?.modelFeatures?.supportsThinking??!0);'
            'setAgApiKey(item?.apiKey||"");'
            'setAgBaseUrl(item?.baseUrl||"https://aiping.cn/api/v1");'
            'setAgEditTarget(targetLabel);'
            'setAgTestStatus("");'
            '}catch(_){}'
            '},[f]);'
            '(0,A.useEffect)(()=>{'
            'if(!a){setAgTestStatus("");setAgTesting(!1);setAgEditTarget(void 0);return;}'
            'try{'
            'var allSaved=window.__agCustomModelsStore?window.__agCustomModelsStore.getModels():{};'
            'setAgSavedMap({...allSaved});'
            'var keys=Object.keys(allSaved);'
            'if(b==="edit"&&e){loadSingleModel(e);}'
            'else if(keys.length>0){'
            'loadSingleModel(keys[keys.length-1]);'
            '}else{'
            'l("");n("");r("128000");setAgApiKey("");setAgBaseUrl("https://aiping.cn/api/v1");u(!0);w(!0);y(!0);setAgEditTarget(void 0);setAgTestStatus("");'
            '}'
            '}catch(_){}'
            '},[a,b,e]);'
            'var H=(0,A.useCallback)(targetToRemove=>{'
            'var delLabel=typeof targetToRemove==="string"?targetToRemove:(agFormRef.current.e||agFormRef.current.k);'
            'if(!delLabel)return;'
            'try{window.__agCustomModelsStore&&window.__agCustomModelsStore.removeModel(delLabel);'
            'setAgSavedMap({...(window.__agCustomModelsStore?window.__agCustomModelsStore.getModels():{})});}catch(_){}'
            'g({type:"removeCustomModel",label:delLabel});'
            'if(delLabel===(agFormRef.current.e||e)){c();}'
            'B("CASCADE_CUSTOM_MODEL_EVENT",{extra:{action:"delete",model_name:delLabel}});'
            '},[g,e,c,B]);'
            'var agTestConn=(0,A.useCallback)(()=>{'
            'var cur=agFormRef.current;'
            'var cModel=(cur.k||"").trim();'
            'var cUrl=(cur.agBaseUrl||"").trim().replace(/\\/+$/,"").replace(/\\/chat\\/completions$/,"")||"https://aiping.cn/api/v1";'
            'var cKey=(cur.agApiKey||"").trim();'
            'if(!cModel){setAgTestStatus("ERR:请先输入模型 ID (如 DeepSeek-V4.1-Flash-1017)");return;}'
            'setAgTesting(!0);setAgTestStatus("WAIT:正在连接 "+cUrl+"/chat/completions 验证模型与密钥...");'
            'setTimeout(()=>{'
            'try{'
            'var res=window.__agCustomModelsStore?window.__agCustomModelsStore.testModel(cUrl,cKey,cModel):"ERR:未找到测试接口";'
            'setAgTestStatus(res);'
            '}catch(err){setAgTestStatus("ERR:"+String(err));}'
            'setAgTesting(!1);'
            '},30);'
            '},[]);'
            'var J=(0,A.useCallback)(()=>{'
            'var cur=agFormRef.current;'
            'var cleanLabel=(cur.k||"").trim();'
            'if(!cleanLabel)return;'
            'var cleanUrl=(cur.agBaseUrl||"").trim().replace(/\\/+$/,"").replace(/\\/chat\\/completions$/,"")||"https://aiping.cn/api/v1";'
            'var cleanKey=(cur.agApiKey||"").trim();'
            'var feat=p(I.ModelFeaturesSchema,{zeroShotCapable:!0,supportsImages:cur.t,supportsToolCalls:cur.v,supportsThinking:cur.x});'
            'var L=p(I.ModelInfoSchema,{modelId:I.Model.GOOGLE_GEMINI_INTERNAL_BYOM,apiProvider:I.APIProvider.API_PROVIDER_GOOGLE_EVERGREEN,chatModelName:cleanLabel,modelName:cleanLabel,maxTokens:Math.max(1024,Math.min(Number(cur.q)||128000,Number.MAX_SAFE_INTEGER)),modelFeatures:feat});'
            'var oldTarget=cur.e;'
            'try{window.__agCustomModelsStore&&window.__agCustomModelsStore.addModel(cleanLabel,L,cleanKey,cleanUrl,oldTarget);}catch(_){}'
            'oldTarget?g({type:"editCustomModel",oldLabel:oldTarget,label:cleanLabel,modelInfo:L,apiKey:cleanKey,baseUrl:cleanUrl}):g({type:"addCustomModel",label:cleanLabel,modelInfo:L,apiKey:cleanKey,baseUrl:cleanUrl});'
            'h({label:cleanLabel,value:I.Model.GOOGLE_GEMINI_INTERNAL_BYOM,isCustom:!0,customModelUrl:cleanLabel,disabled:!1});'
            'B("CASCADE_CUSTOM_MODEL_EVENT",{extra:{action:oldTarget?"edit":"add",model_name:cleanLabel}});'
            'c();'
            '},[g,k,m,q,t,v,x,c,e,b,B,h,agApiKey,agBaseUrl,agEditTarget]),'
            'K=L=>{(L.metaKey||L.ctrlKey)&&L.key==="a"&&(L.preventDefault(),L.currentTarget.select())};'
            'var savedEntries=Object.entries(agSavedMap||{});'
            'var previewEndpoint=((agBaseUrl||"").trim().replace(/\\/+$/,"").replace(/\\/chat\\/completions$/,"")||"https://aiping.cn/api/v1")+"/chat/completions";'
            'var presets=[{name:"AI Ping",url:"https://aiping.cn/api/v1"},{name:"DeepSeek官方",url:"https://api.deepseek.com/v1"},{name:"硅基流动",url:"https://api.siliconflow.cn/v1"},{name:"阿里云百炼",url:"https://dashscope.aliyuncs.com/compatible-mode/v1"},{name:"OpenRouter",url:"https://openrouter.ai/api/v1"}];'
            'var modelPresets=["DeepSeek-V4.1-Flash-1017","deepseek-chat","deepseek-reasoner"];'
            'return A.createElement(NC,{isOpen:a,onClose:c,onSubmit:J,title:(agEditTarget||b==="edit")?"编辑第三方 API 模型 (Edit Model)":"添加第三方 API 模型 (Add Custom Model)",className:"w-[94vw] max-w-[520px] rounded-lg"},'
            'A.createElement("div",{className:"flex w-full flex-col items-start justify-start gap-3 max-h-[78vh] overflow-y-auto pr-0.5"},'
            # Saved models quick bar
            'savedEntries.length>0&&A.createElement("div",{className:"w-full rounded-md border border-border bg-muted/40 p-2 flex flex-col gap-1.5"},'
            'A.createElement("div",{className:"flex items-center justify-between text-xs text-muted-foreground"},'
            'A.createElement("span",{className:"font-medium text-foreground"},"已保存的模型 (点击切换编辑):"),'
            'A.createElement("button",{type:"button",onClick:()=>{l("");n("");setAgEditTarget(void 0);setAgTestStatus("")},className:"text-xs text-primary hover:underline cursor-pointer bg-transparent border-none p-0"},"+ 新建模型")),'
            'A.createElement("div",{className:"flex flex-wrap gap-1.5"},savedEntries.map(([sLabel,sData])=>{'
            'var isEditingThis=(agEditTarget||e)===sLabel||k===sLabel;'
            'var shortHost=(sData?.baseUrl||"").replace(/^https?:\\/\\//,"").split("/")[0]||"api";'
            'return A.createElement("div",{key:sLabel,className:aj("flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-colors",isEditingThis?"border-primary bg-primary/15 text-foreground font-medium":"border-border bg-background text-secondary-foreground")},'
            'A.createElement("button",{type:"button",onClick:()=>loadSingleModel(sLabel),className:"bg-transparent border-none p-0 text-left cursor-pointer text-inherit flex items-center gap-1"},'
            'A.createElement("span",{className:"truncate max-w-[160px]"},sLabel),'
            'A.createElement("span",{className:"opacity-60 text-[10px]"},`(${shortHost})`)),'
            'A.createElement("button",{type:"button",title:"删除该模型",onClick:ev=>{ev.stopPropagation();H(sLabel)},className:"ml-1 rounded px-1 text-muted-foreground hover:bg-destructive hover:text-destructive-foreground cursor-pointer border-none bg-transparent"},"×"))'
            '}))),'
            # Main Form Grid
            'A.createElement("div",{className:"grid w-full grid-cols-1 gap-3"},'
            # 1. Model ID
            'A.createElement("div",{className:"flex flex-col gap-1"},'
            'A.createElement("div",{className:"flex items-center justify-between"},'
            'A.createElement("label",{htmlFor:C,className:"text-sm font-medium"},"1. 模型 ID (Model ID)"),'
            'k&&A.createElement("button",{type:"button",onClick:()=>{l("");n("");setAgTestStatus("")},className:"text-xs text-muted-foreground hover:text-foreground bg-transparent border-none cursor-pointer p-0"},"清空")),'
            'A.createElement("div",{className:"flex flex-wrap gap-1 mb-0.5"},modelPresets.map(mp=>'
            'A.createElement("button",{key:mp,type:"button",onClick:()=>{l(mp);n(mp);if(mp.includes("1017"))setAgBaseUrl("https://aiping.cn/api/v1");setAgTestStatus("")},className:aj("rounded border px-1.5 py-0.5 text-[11px] cursor-pointer transition-colors",k===mp?"border-primary bg-primary/15 text-foreground":"border-border bg-muted/50 text-muted-foreground hover:text-foreground")},mp))),'
            'A.createElement("div",{className:"bg-muted rounded-md w-full border border-border focus-within:border-primary"},'
            'A.createElement("input",{id:C,type:"text",value:k,onChange:L=>{var val=L.target.value;l(val);n(val);setAgTestStatus("")},onKeyDown:K,className:"w-full rounded-md border-none bg-background p-2 text-sm text-foreground outline-none placeholder:text-muted-foreground",placeholder:"例如: DeepSeek-V4.1-Flash-1017"}))),'
            # 2. API Base URL
            'A.createElement("div",{className:"flex flex-col gap-1"},'
            'A.createElement("div",{className:"flex items-center justify-between"},'
            'A.createElement("label",{className:"text-sm font-medium"},"2. API Base URL (接口地址)"),'
            'agBaseUrl&&A.createElement("button",{type:"button",onClick:()=>{setAgBaseUrl("");setAgTestStatus("")},className:"text-xs text-muted-foreground hover:text-foreground bg-transparent border-none cursor-pointer p-0"},"清空")),'
            'A.createElement("div",{className:"flex flex-wrap gap-1 mb-0.5"},presets.map(pr=>'
            'A.createElement("button",{key:pr.name,type:"button",onClick:()=>{setAgBaseUrl(pr.url);setAgTestStatus("")},className:aj("rounded border px-1.5 py-0.5 text-[11px] cursor-pointer transition-colors",(agBaseUrl||"").trim().replace(/\\/+$/,"")===pr.url?"border-primary bg-primary/15 text-foreground font-medium":"border-border bg-muted/50 text-muted-foreground hover:text-foreground")},pr.name))),'
            'A.createElement("div",{className:"bg-muted rounded-md w-full border border-border focus-within:border-primary"},'
            'A.createElement("input",{type:"text",value:agBaseUrl,onChange:L=>{setAgBaseUrl(L.target.value);setAgTestStatus("")},onKeyDown:K,className:"w-full rounded-md border-none bg-background p-2 text-sm text-foreground outline-none placeholder:text-muted-foreground",placeholder:"例如: https://aiping.cn/api/v1"})),'
            'A.createElement("span",{className:"text-[11px] text-muted-foreground break-all"},`实际请求端点: ${previewEndpoint}`)),'
            # 3. API Key
            'A.createElement("div",{className:"flex flex-col gap-1"},'
            'A.createElement("div",{className:"flex items-center justify-between"},'
            'A.createElement("label",{className:"text-sm font-medium"},"3. API Key (接口密钥)"),'
            'A.createElement("div",{className:"flex items-center gap-2"},'
            'A.createElement("button",{type:"button",onClick:()=>setShowAgKey(!showAgKey),className:"text-xs text-primary hover:underline bg-transparent border-none cursor-pointer p-0"},showAgKey?"隐藏密钥":"显示密钥"),'
            'agApiKey&&A.createElement("button",{type:"button",onClick:()=>{setAgApiKey("");setAgTestStatus("")},className:"text-xs text-muted-foreground hover:text-foreground bg-transparent border-none cursor-pointer p-0"},"清空"))),'
            'A.createElement("div",{className:"bg-muted rounded-md w-full border border-border focus-within:border-primary"},'
            'A.createElement("input",{type:showAgKey?"text":"password",value:agApiKey,onChange:L=>{setAgApiKey(L.target.value);setAgTestStatus("")},onKeyDown:K,className:"w-full rounded-md border-none bg-background p-2 text-sm text-foreground outline-none placeholder:text-muted-foreground font-mono",placeholder:"粘贴您的 API Key (如 sk-...)"}))),'
            # 4. Compact Max Tokens & Capabilities
            'A.createElement("div",{className:"rounded-md border border-border bg-muted/20 p-2 flex flex-col gap-2"},'
            'A.createElement("div",{className:"flex items-center justify-between gap-2"},'
            'A.createElement("label",{htmlFor:E,className:"text-xs text-muted-foreground"},"上下文窗口 (Max Tokens):"),'
            'A.createElement("input",{id:E,type:"number",value:q,onChange:L=>{r(L.target.value)},onKeyDown:K,className:"w-28 rounded border border-border bg-background px-2 py-1 text-xs text-foreground outline-none"})),'
            'A.createElement("div",{className:"flex flex-wrap items-center gap-4 pt-0.5"},'
            'A.createElement("label",{className:"flex items-center gap-1.5 cursor-pointer text-xs"},A.createElement("input",{type:"checkbox",checked:v,onChange:L=>w(L.target.checked)}),"工具调用 (Tool Calls)"),'
            'A.createElement("label",{className:"flex items-center gap-1.5 cursor-pointer text-xs"},A.createElement("input",{type:"checkbox",checked:x,onChange:L=>y(L.target.checked)}),"深度思考 (Thinking)"),'
            'A.createElement("label",{className:"flex items-center gap-1.5 cursor-pointer text-xs"},A.createElement("input",{type:"checkbox",checked:t,onChange:L=>u(L.target.checked)}),"图片输入 (Images)"))),'
            # 5. Connection Test Result Banner
            'agTestStatus&&A.createElement("div",{className:aj("w-full rounded-md border p-2 text-xs break-all whitespace-pre-wrap",agTestStatus.startsWith("OK:")?"border-green-500/50 bg-green-500/10 text-green-400":agTestStatus.startsWith("WAIT:")?"border-blue-500/50 bg-blue-500/10 text-blue-300":"border-red-500/50 bg-red-500/10 text-red-400")},'
            'agTestStatus.replace(/^(OK:|ERR:|WAIT:)/,""))),'
            # 6. Footer Action Buttons
            'A.createElement("div",{className:"flex w-full items-center justify-between gap-2 pt-2 border-t border-border"},'
            'A.createElement("button",{type:"button",disabled:agTesting||!k.trim(),onClick:agTestConn,className:"rounded-md border border-border bg-secondary px-2.5 py-1.5 text-xs font-medium text-foreground hover:opacity-90 disabled:opacity-50 cursor-pointer"},agTesting?"⏳ 测试中...":"⚡ 测试连接"),'
            'A.createElement("div",{className:"flex items-center gap-2"},'
            'A.createElement(tA,{size:"md",variant:"ghost",onClick:c},"取消"),'
            '(agEditTarget||b==="edit")&&A.createElement(tA,{size:"md",variant:"destructive",onClick:()=>H(agEditTarget||e)},"删除"),'
            'A.createElement("button",{type:"button",onClick:J,disabled:!k.trim(),className:"hover:opacity-90 rounded-md flex items-center gap-1 border-none bg-primary px-3.5 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"},"保存并使用")))))}'
        )
        content = content[:idx_gzb_start] + new_gzb + content[idx_gzb_end:]
        print("[web-patch] Upgraded Gzb Custom Model modal with presets, show/hide key, saved chips, and live test")
    else:
        print("[web-patch] WARNING: Could not locate Gzb block in main.js!", file=sys.stderr)

    # 6. Appearance settings Desktop Mode hook
    hook_pattern = re.compile(r'(var\s+[A-Za-z0-9_$]+=[A-Za-z0-9_$]+!==3,\s*[A-Za-z0-9_$]+=[A-Za-z0-9_$]+!==2,\s*[A-Za-z0-9_$]+=[A-Za-z0-9_$]+=>\s*[A-Za-z0-9_$]+=>\{.*?\};)')
    hook_match = hook_pattern.search(content)

    theme_idx = content.find('{label:"Theme"')
    theme_match = None
    react_id = "A"
    if theme_idx != -1:
        window_start = max(0, theme_idx - 100)
        window_end = min(len(content), theme_idx + 500)
        window_text = content[window_start:window_end]
        theme_pattern = re.compile(
            r'([A-Za-z0-9_$]+)\.createElement\(([A-Za-z0-9_$]+),\{label:"Theme",.*?onSelect:[A-Za-z0-9_$]+\}\)'
        )
        theme_match = theme_pattern.search(window_text)
        if theme_match:
            react_id = theme_match.group(1)

    if hook_match and theme_match and ("Desktop Mode" not in content):
        orig_hook = hook_match.group(1)
        injected_hook = (
            f"var [isDesktop,setIsDesktop]=(0,{react_id}.useState)(()=>{{"
            "try{if(window.Android&&typeof window.Android.isDesktopMode==='function')return window.Android.isDesktopMode();"
            "var s=localStorage.getItem('ag_desktop_mode');return s===null?!1:s==='true'}catch(_){return !1}});"
            f"var onDesktopToggle=(0,{react_id}.useCallback)(v=>{{"
            "setIsDesktop(v);try{localStorage.setItem('ag_desktop_mode',String(v));"
            "if(window.Android&&typeof window.Android.setDesktopMode==='function')window.Android.setDesktopMode(v)}catch(_){}},[]);"
            + orig_hook
        )
        item_comp = "v3"
        switch_comp = "dX"
        re_idx = content.find('rightElement:')
        if re_idx != -1:
            re_window = content[max(0, re_idx - 150):min(len(content), re_idx + 150)]
            item_m = re.search(r'([A-Za-z0-9_$]+)\.createElement\(([A-Za-z0-9_$]+),\{label:[^,]+,description:[^,]+,rightElement:', re_window)
            if item_m:
                item_comp = item_m.group(2)
            sw_m = re.search(r'rightElement:[A-Za-z0-9_$]+\.createElement\(([A-Za-z0-9_$]+),\{checked:', re_window)
            if sw_m:
                switch_comp = sw_m.group(1)

        orig_theme = theme_match.group(0)
        injected_theme = (
            orig_theme
            + f',{react_id}.createElement({item_comp},{{label:"Desktop Mode",description:"Use desktop viewport and user agent for the workspace",'
            + f'rightElement:{react_id}.createElement({switch_comp},{{checked:isDesktop,onCheckedChange:onDesktopToggle}})}})'
        )
        content = content.replace(orig_hook, injected_hook, 1)
        content = content.replace(orig_theme, injected_theme, 1)

    # 7a. Open Folder initialPath defaults to /storage/emulated/0
    wqc_target = 'initialPath:b?b.fsPath:ch?"C:/":"/"'
    if wqc_target in content:
        content = content.replace(wqc_target, 'initialPath:"/storage/emulated/0"', 1)
        print("[web-patch] Defaulted Open Folder initialPath to /storage/emulated/0")

    # 7b. Interactive Folder Picker (iqb) quick-jump shortcuts to Shared Storage
    iqb_b_target = 'var K=D.replace(wY,"")===k.replace(wY,""),L={type:"basic",item:{id:`parent:${D}`,label:"..",icon:A.createElement(W,{name:"arrow_upward",size:16}),_isDir:!0,_isParent:!0}},M=t.map(N=>({type:"basic",item:{id:N.id,label:N.label,\nicon:A.createElement(W,{name:N.isDir?"folder":"description",size:16}),_isDir:N.isDir}}));return[{id:"confirm-group",items:K?[]:[L]},{id:"contents-group",items:M}]'
    iqb_b_repl = (
        'var K=D.replace(wY,"")===k.replace(wY,""),'
        'L={type:"basic",item:{id:`parent:${D}`,label:".. (上级目录)",icon:A.createElement(W,{name:"arrow_upward",size:16}),_isDir:!0,_isParent:!0}},'
        'agSd={type:"basic",item:{id:"parent:/storage/emulated/0",label:"📁 手机内部存储 (/storage/emulated/0)",icon:A.createElement(W,{name:"sd_card",size:16}),_isDir:!0}},'
        'agDoc={type:"basic",item:{id:"parent:/storage/emulated/0/Documents",label:"📂 公共文档 (/storage/emulated/0/Documents)",icon:A.createElement(W,{name:"folder",size:16}),_isDir:!0}},'
        'agPrj={type:"basic",item:{id:"parent:/storage/emulated/0/Documents/Antigravity",label:"🚀 Antigravity工程目录",icon:A.createElement(W,{name:"star",size:16}),_isDir:!0}},'
        'M=t.map(N=>({type:"basic",item:{id:N.id,label:N.label,\nicon:A.createElement(W,{name:N.isDir?"folder":"description",size:16}),_isDir:N.isDir}}));'
        'return[{id:"confirm-group",items:[...(K?[]:[L]),agSd,agDoc,agPrj]},{id:"contents-group",items:M}]'
    )
    if iqb_b_target in content:
        content = content.replace(iqb_b_target, iqb_b_repl, 1)
        print("[web-patch] Added quick-jump storage shortcuts to iqb folder picker")

    iqb_h_target = 'if(K.id===`confirm:${k}`)c(k),e();else if(K.id===`parent:${D}`)E(D);'
    iqb_h_repl = 'if(K.id===`confirm:${k}`)c(k),e();else if(K.id&&K.id.startsWith("parent:"))E(K.id.slice(7));'
    if iqb_h_target in content:
        content = content.replace(iqb_h_target, iqb_h_repl, 1)
        print("[web-patch] Enabled quick-jump navigation in iqb folder picker")

    # 7c. Default Workspaces list to include /storage/emulated/0/Documents/Antigravity and /storage/emulated/0
    qqc_target = 'f=vm(a.getState());b=e(f);'
    qqc_repl = (
        'f=vm(a.getState());b=e(f);'
        'if(!b||b.length===0){b=['
        '{uri:"file:///storage/emulated/0/Documents/Antigravity",label:"Antigravity (公共项目目录)"},'
        '{uri:"file:///storage/emulated/0",label:"手机内部存储 (/storage/emulated/0)"}'
        '];}'
    )
    if qqc_target in content:
        content = content.replace(qqc_target, qqc_repl, 1)
        print("[web-patch] Pre-populated default workspaces with shared storage")

    # 8. Background Resume Trajectory Stream Sync (vKa)
    vka_target = 'this._factory=a}'
    vka_repl = (
        'this._factory=a;'
        'this.refreshTrajectories=()=>{try{if(!this._factory)return;'
        'for(let [c,e]of this.JSC$7869__states.entries()){let f=e;f.link.dispose();f.underlyingProvider.dispose();f.underlyingProvider=this._factory(c);f.link=Hja(f.underlyingProvider,f.provider,{omitInitial:!0});}'
        '}catch(err){console.warn("[AGY ResumeSync] refreshTrajectories err",err)}};'
        'window.__agTrajectoriesRegistry=this;'
        'window.__agRefreshTrajectories=s=>{console.log("[AGY ResumeSync] Refreshing active trajectories triggered by",s);this.refreshTrajectories()}}'
    )
    if vka_target in content and "agTrajectoriesRegistry" not in content:
        content = content.replace(vka_target, vka_repl, 1)
        print("[web-patch] Exposed window.__agTrajectoriesRegistry & __agRefreshTrajectories in vKa")

    vka_disp_target = 'dispose(){for(let [a]of this.JSC$7869__states.entries())this._disposeEntry(a)}'
    vka_disp_repl = 'dispose(){if(window.__agTrajectoriesRegistry===this){window.__agTrajectoriesRegistry=void 0;window.__agRefreshTrajectories=void 0}for(let [a]of this.JSC$7869__states.entries())this._disposeEntry(a)}'
    if vka_disp_target in content:
        content = content.replace(vka_disp_target, vka_disp_repl, 1)
        print("[web-patch] Cleaned up global registry on vKa dispose")
    # 9. Chinese Localization (Web UI Phase 2 - 附件菜单、输入框及主界面全套汉化)
    # 9a. Add Context 按钮、浮层标题与提示
    content = content.replace('A.createElement(WL,null,"Add Context")', 'A.createElement(WL,null,"添加上下文")')
    content = content.replace('A.createElement(ty,{id:g,place:"top"},"Add Context")', 'A.createElement(ty,{id:g,place:"top"},"添加上下文")')
    content = content.replace('"aria-label":"Add context"', '"aria-label":"添加上下文"')

    # 9b. Add Context 下拉菜单项目 (图片/媒体、文件夹、提及、快捷指令、浏览器、录屏)
    content = content.replace('className:Fa.className}),label:"Media",onClick:ra', 'className:Fa.className}),label:"图片 / 媒体",onClick:ra')
    content = content.replace('className:Fa.className}),label:"Folder",onClick:()=>void n()', 'className:Fa.className}),label:"文件夹",onClick:()=>void n()')
    content = content.replace('className:Fa.className}),label:"Mentions",onClick:Aa', 'className:Fa.className}),label:"提及 (@)",onClick:Aa')
    content = content.replace('className:Fa.className}),label:"Actions",onClick:na', 'className:Fa.className}),label:"快捷指令 (/)",onClick:na')
    content = content.replace('icon:Nq,label:"Browser",onClick:Ca', 'icon:Nq,label:"智能体浏览器",onClick:Ca')
    content = content.replace('className:Fa.className}),label:"Screen Recording",onClick:u', 'className:Fa.className}),label:"屏幕录制",onClick:u')
    content = content.replace('label:"Getting scripts..."', 'label:"正在获取自定义脚本..."')

    # 9c. 底部输入框默认引导词 (Placeholder)
    content = content.replace('"Ask anything, @ to mention"', '"输入任何需求，@ 引用"')
    content = content.replace('", / for actions"', '"，/ 快捷指令"')
    content = content.replace('"Message subagent, @ to mention"', '"向子智能体发送消息，@ 引用"')

    # 9d. 侧边栏与项目列表导航（全面汉化）
    content = content.replace('text:"New Conversation",href:', 'text:"新建对话",href:')
    content = content.replace('tooltipText:"New Conversation",tooltipKeybinding:Dz', 'tooltipText:"新建对话",tooltipKeybinding:Dz')
    content = content.replace('text:"Conversation History",href:', 'text:"对话历史",href:')
    content = content.replace('tooltipText:"Conversation History",tooltipKeybinding:mLa', 'tooltipText:"对话历史",tooltipKeybinding:mLa')
    content = content.replace('schedule:{title:"Scheduled Tasks",sidebarLabel:"Scheduled Tasks"', 'schedule:{title:"定时任务",sidebarLabel:"定时任务"')
    content = content.replace('text:"Settings",onClick:', 'text:"系统设置",onClick:')
    content = content.replace('tooltipText:"Settings",tooltipKeybinding:Ek', 'tooltipText:"系统设置",tooltipKeybinding:Ek')
    content = content.replace('wa=f==="none"||f==="status"?"Conversations":E?"Workspaces":"Projects"', 'wa=f==="none"||f==="status"?"对话列表":E?"工作区":"项目列表"')
    content = content.replace('var ua=v?`${wa} (Archived)`:wa', 'var ua=v?`${wa} (已归档)`:wa')
    content = content.replace('ariaLabel:E?"Add Workspace":"Create New Project"', 'ariaLabel:E?"添加工作区":"创建新项目"')
    content = content.replace('E?"Add Workspace":"Create New Project"),A.createElement(ty,{id:la,place:"top"},"Display Options"', 'E?"添加工作区":"创建新项目"),A.createElement(ty,{id:la,place:"top"},"显示偏好设置"')
    content = content.replace('qa.length>0&&da.push({id:"standalone",label:"Conversations",items:qa})', 'qa.length>0&&da.push({id:"standalone",label:"对话列表",items:qa})')
    content = content.replace('[{id:"all",label:"Conversations",items:ha}]', '[{id:"all",label:"对话列表",items:ha}]')
    content = content.replace('ma==="standalone"?ja="Standalone":', 'ma==="standalone"?ja="未归档会话":')
    content = content.replace('groupId:v.id,label:"No conversations yet"', 'groupId:v.id,label:"暂无历史对话"')
    content = content.replace(':"No conversations yet"', ':"暂无历史对话"')
    content = content.replace('label:l?.label||g.find(n=>n.project.id===k)?.project.name||"Unknown Project"', 'label:l?.label||g.find(n=>n.project.id===k)?.project.name||"默认项目"')
    content = content.replace('select-none"},"Projects")', 'select-none"},"项目列表")')
    content = content.replace('v?"Show Less":"Show All"', 'v?"收起":"展开全部"')
    content = content.replace('select-none"},"Not in Project")', 'select-none"},"未归档项目")')
    content = content.replace('text:"Conversations",onClick:', 'text:"对话历史",onClick:')
    content = content.replace('text:"Shortcuts",\nonClick:', 'text:"快捷键",\nonClick:')
    content = content.replace('text:"Provide Feedback",onClick:', 'text:"提供反馈",onClick:')
    content = content.replace('var k=g||h||"Account";', 'var k=g||h||"账号设置";')
    content = content.replace('B?"Workspaces":"Projects"', 'B?"工作区":"项目列表"')

    # 9e. 顶部主聊天区工作区选择器
    content = content.replace('c?"No Project":Ca?Aa?.project?.name??x:x;', 'c?"无所属项目":Ca?Aa?.project?.name??x:x;')
    content = content.replace('className:"truncate flex-grow min-w-0"},"No Project")', 'className:"truncate flex-grow min-w-0"},"无所属项目")')
    content = content.replace('x=x?"Select Workspace":"Select Project";', 'x=x?"选择工作区":"选择项目";')
    content = content.replace('x=ea?"New Workspace":', 'x=ea?"新建工作区":')

    # 9f. 智能体思考状态与实时步骤 (Working, Thinking, Running, Waiting 等)
    content = content.replace('case 4:return"Running";case 3:return"Waiting";case 5:return"Agent is analyzing videos";case 2:return"Thinking";', 'case 4:return"正在运行...";case 3:return"等待中...";case 5:return"正在分析视频...";case 2:return"正在思考...";')
    content = content.replace('return a?`Executing task: ${a}`:"Working"}else return"Agent Stopped"', 'return a?`正在执行任务: ${a}`:"正在执行..."}else return"智能体已停止"')
    content = content.replace('(b?"Compacting":"Working")', '(b?"整理压缩中...":"正在执行...")')
    content = content.replace('c.status===T.CortexStepStatus.RUNNING&&Qm("Working...")', 'c.status===T.CortexStepStatus.RUNNING&&Qm("正在执行...")')
    content = content.replace('(e=b??e[e.length-1])?HSb(e,c):"Working":"Thinking"', '(e=b??e[e.length-1])?HSb(e,c):"正在执行...":"正在思考..."')
    content = content.replace('F?"Working...":l?.createdAtMs', 'F?"正在执行...":l?.createdAtMs')
    content = content.replace('l.liveToolSummary??"Working...":', 'l.liveToolSummary??"正在执行...":')
    content = content.replace('`Worked for ${cN(l.lastModifiedAtMs-l.createdAtMs)}`', '`执行耗时 ${cN(l.lastModifiedAtMs-l.createdAtMs)}`')
    content = content.replace('`${l.terminatedEarly?"Stopped after":"Worked for"} ${cN(l.completedAtMs-l.createdAtMs)}`', '`${l.terminatedEarly?"中途停止于":"执行耗时"} ${cN(l.completedAtMs-l.createdAtMs)}`')
    content = content.replace(':"Thought Process"', ':"思考过程"')
    content = content.replace('label:"Accept Step"', 'label:"采纳此步骤"')
    content = content.replace('label:"Reject Step"', 'label:"拒绝此步骤"')
    content = content.replace('label:"New Conversation"', 'label:"新建对话"')
    content = content.replace('label:"Open Folder"', 'label:"打开文件夹"')
    content = content.replace('Thought for ${Math.max(1,Number(b.seconds))}s', '思考耗时 ${Math.max(1,Number(b.seconds))} 秒')
    content = content.replace('Thought for ${Math.max(1,Number(H.seconds))}s', '思考耗时 ${Math.max(1,Number(H.seconds))} 秒')

    # 9g. 已排队消息卡片 (Queued Messages) 与操作按钮
    content = content.replace('A.createElement("span",{className:"shrink-0"},"Queued Messages")', 'A.createElement("span",{className:"shrink-0"},"已排队消息")')
    content = content.replace('"Sends after agent finishes working"', '"智能体执行完成后自动发送"')
    content = content.replace('tooltip:"Send Now",', 'tooltip:"立即发送",')
    content = content.replace('tooltip:"Edit",', 'tooltip:"编辑",')
    content = content.replace('tooltip:"Delete",', 'tooltip:"删除",')
    content = content.replace('Qm("Queued message deleted")', 'Qm("已删除排队消息")')
    content = content.replace('a===1?"Message queued.":`Message queued. ${a} messages in queue.`', 'a===1?"消息已加入队列。":`消息已加入队列，当前共 ${a} 条排队。`')

    # 9h. 应用侧边栏顶部品牌标题
    content = content.replace('nameShort:m,nameLong:m,', 'nameShort:"Antigravity",nameLong:"Antigravity",')

    # 9i. 对话右键/悬浮操作菜单 (Pin, Unpin, Rename, Archive, Delete 等)
    content = content.replace('label:Ka?"Unpin":"Pin"', 'label:Ka?"取消置顶":"置顶"')
    content = content.replace('label:Kg?"Mark Read":"Mark Unread"', 'label:Kg?"标记为已读":"标记为未读"')
    content = content.replace('Sd=[{id:"rename",label:"Rename",', 'Sd=[{id:"rename",label:"重命名",')
    content = content.replace('id:"restore",label:"Restore",', 'id:"restore",label:"恢复",')
    content = content.replace('id:"delete",label:"Delete Permanently",', 'id:"delete",label:"永久删除",')
    content = content.replace('id:"archive",label:"Archive",', 'id:"archive",label:"归档",')
    content = content.replace('id:"delete",label:"Delete",', 'id:"delete",label:"删除",')
    content = content.replace('label:"Pin This Conversation"', 'label:"置顶此对话"')
    content = content.replace('label:"Unpin This Conversation"', 'label:"取消置顶"')
    content = content.replace('label:"Rename This Conversation"', 'label:"重命名此对话"')
    content = content.replace('label:"Archive This Conversation"', 'label:"归档此对话"')
    content = content.replace('label:"Copy Conversation Markdown"', 'label:"复制对话为 Markdown"')
    content = content.replace('label:"Copy Conversation ID"', 'label:"复制会话 ID"')
    content = content.replace('label:"Mark This Conversation as Read"', 'label:"标记为已读"')
    content = content.replace('label:"Mark This Conversation as Unread"', 'label:"标记为未读"')
    content = content.replace('label:"Find in Conversation"', 'label:"在对话中查找"')
    content = content.replace('label:"Move to New Group"', 'label:"移动到新分组"')
    content = content.replace('label:"Remove from Group"', 'label:"从分组中移出"')
    content = content.replace('title:"Delete Conversation"', 'title:"删除对话"')
    content = content.replace('"Are you sure you want to delete this conversation? This action cannot be undone."', '"确定要删除此对话吗？此操作无法撤销。"')

    # 9j. 消息气泡操作菜单与代码块复制
    content = content.replace('id:"copy-message",label:"Copy",', 'id:"copy-message",label:"复制消息",')
    content = content.replace('id:"undo-to-here",label:"Undo To Here",', 'id:"undo-to-here",label:"撤销至此处",')
    content = content.replace('f?"Copied":"Copy code"', 'f?"已复制":"复制代码"')
    content = content.replace('u?"Copied":"Copy image"', 'u?"已复制":"复制图片"')
    content = content.replace('e?"Copied":"Copy link"', 'e?"已复制":"复制链接"')
    content = content.replace('Qm("Copied to clipboard")', 'Qm("已复制到剪贴板")')

    # 9k. 底部模型选择器思考强度档位 (Thinking Effort)
    content = content.replace('EXb={low:"Low",medium:"Medium",high:"High",xhigh:"Extra",max:"Max"}', 'EXb={low:"低思考 (Low)",medium:"中等思考 (Medium)",high:"深度思考 (High)",xhigh:"长思考 (Extra)",max:"最大思考 (Max)"}')
    content = content.replace('n?"Best of N Models":\n"Model"', 'n?"多模型对比模式":\n"模型选择"')

    # 9l. 侧边栏显示偏好与排序 (Display Options / Sort By / Group By)
    content = content.replace('title:"Group By"', 'title:"分组方式"')
    content = content.replace('title:"Sort By"', 'title:"排序方式"')
    content = content.replace('K_={last_updated:"Last Updated",last_user_prompt:"Last Prompt",custom:"Custom Order"}', 'K_={last_updated:"最近更新",last_user_prompt:"最近提问",custom:"自定义顺序"}')
    content = content.replace('title:"Filter"', 'title:"筛选过滤"')
    content = content.replace('title:"Display"', 'title:"显示内容"')
    content = content.replace('"Only Unread"', '"仅未读"')
    content = content.replace('"Archived Only"', '"仅显示已归档"')

    # 9m. 项目与工作区创建菜单
    content = content.replace('label:"New Workspace",tooltipText:', 'label:"新建工作区",tooltipText:')
    content = content.replace('label:"Create Project",\ntooltipText:', 'label:"创建新项目",\ntooltipText:')
    content = content.replace('label:"New Project",tooltipText:"Select a folder."', 'label:"新建项目",tooltipText:"选择一个文件夹作为项目"')

    # 9n. 常用搜索框占位符 (Search Placeholders)
    content = content.replace('placeholder:"Search conversations...",value:b', 'placeholder:"搜索历史对话...",value:b')
    content = content.replace('placeholder:"Search conversations...",value:e', 'placeholder:"搜索历史对话...",value:e')
    content = content.replace('placeholder:"Search for conversations...",prefix:', 'placeholder:"搜索历史对话...",prefix:')
    content = content.replace('placeholder:"Search for commands...",', 'placeholder:"搜索快捷命令...",')
    content = content.replace('placeholder:"Search file contents...",', 'placeholder:"搜索代码与文件内容...",')
    content = content.replace('placeholder:"Search projects...",', 'placeholder:"搜索项目...",')
    content = content.replace('placeholder:"Search workspaces...",', 'placeholder:"搜索工作区...",')

    # 9o. 权限请求提示与子智能体控制
    content = content.replace('label:"Always Allow",onClick:', 'label:"始终允许",onClick:')
    content = content.replace('label:"Allow Once",onClick:', 'label:"仅允许本次",onClick:')
    content = content.replace('label:"Deny",onClick:', 'label:"拒绝",onClick:')
    content = content.replace('`Agent needs permission to act on ${l}`', '`智能体需要访问 ${l} 的权限`')
    content = content.replace('tooltip:"Stop Subagent",', 'tooltip:"停止子智能体",')
    content = content.replace('tooltip:"Stop All Subagents",', 'tooltip:"停止所有子智能体",')
    content = content.replace('title:"View child subagents"', 'title:"查看子智能体"')
    content = content.replace('"Welcome to ",a', '"欢迎使用 ",a')

    # 标记已完成第二阶段汉化，避免重复修补
    content += "\n/* agI18nPhase2 */\n"
    print("[web-patch] Applied Phase 2 Chinese translations")

    # 10. Chinese Localization (Web UI Phase 3 - 设置中心、快捷键、文件管理器与 Git 版本控制)
    phase3_replacements = [
        # 10a. 设置中心侧边栏与页面注册表 (web 数组)
        ('var web=[{screen:"General"},{screen:"App",label:"Application"},{screen:"Appearance"},{screen:"Project 4K"},{screen:"Notifications"},{screen:"Models"},{screen:"Customizations"},{screen:"Developer"},{screen:"Tab"},{screen:"Editor"},{screen:"Jetski Chat"},{screen:"Regroup Google3 Chats"}]',
         'var web=[{screen:"General",label:"通用设置"},{screen:"App",label:"应用配置"},{screen:"Appearance",label:"外观与主题"},{screen:"Project 4K",label:"Project 4K 模式"},{screen:"Notifications",label:"通知与声音"},{screen:"Models",label:"模型配置"},{screen:"Customizations",label:"技能与自定义"},{screen:"Developer",label:"开发者选项"},{screen:"Tab",label:"代码补全 (Tab)"},{screen:"Editor",label:"编辑器设置"},{screen:"Jetski Chat",label:"团队对话"},{screen:"Regroup Google3 Chats",label:"会话整理"}]'),

        # 10b. 设置页面标题映射表 (Gtb)
        ('const Gtb=new Map(Object.entries({Account:"Account",Permissions:"Permissions",Agent:"DoNotUseOneMoment",General:"General",Appearance:"Appearance",Project4k:"Project 4K",Tab:"Tab",Editor:"Editor",Browser:"Browser",Notifications:"Notifications",ProvideFeedback:"Provide Feedback",Customization:"Customizations",Models:"Models",App:"App",ProjectGeneral:"Project General",ProjectFolders:"Project Folders",ProjectAgent:"Project Agent",Shortcuts:"Shortcuts",JetskiChat:"Jetski Chat",Developer:"Developer",Google3Migration:"Regroup Google3 Chats"}).map(([a,\nb])=>[a.toLowerCase(),b]));',
         'const Gtb=new Map(Object.entries({Account:"账号设置",Permissions:"权限设置",Agent:"智能体设置",General:"通用设置",Appearance:"外观与主题",Project4k:"Project 4K 模式",Tab:"代码补全 (Tab)",Editor:"编辑器设置",Browser:"浏览器设置",Notifications:"通知与声音",ProvideFeedback:"提供反馈",Customization:"技能与自定义",Models:"模型配置",App:"应用配置",ProjectGeneral:"项目常规",ProjectFolders:"项目目录",ProjectAgent:"项目智能体",Shortcuts:"快捷键",JetskiChat:"团队对话",Developer:"开发者选项",Google3Migration:"会话整理"}).map(([a,\nb])=>[a.toLowerCase(),b]));'),

        # 10c. 设置页面主标题与说明 (G_ 头部组件)
        ('{title:"General",description:"Configure agent execution, queued message delivery, and permissions."}',
         '{title:"通用设置",description:"配置智能体执行策略、排队消息发送以及全局权限控制。"}'),
        ('''{title:"Appearance",description:"Configure the agent's visual theme and display preferences."}''',
         '{title:"外观与主题",description:"自定义智能体界面的视觉主题与显示偏好。"}'),
        ('{title:"Account",description:"Manage your plan, credentials, and general preferences."}',
         '{title:"账号设置",description:"管理您的账户、套餐方案、凭据与全局偏好。"}'),
        ('{title:"Notifications",description:"Manage your notification preferences."}',
         '{title:"通知设置",description:"管理桌面与系统状态栏通知偏好。"}'),
        ('{title:"Shortcuts",description:"Keyboard shortcuts for quick navigation and control."}',
         '{title:"快捷键",description:"用于快速导航与交互控制的键盘快捷键。"}'),
        ('{title:"Tab",description:"Configure tab completion, suggestions, and navigation behavior."}',
         '{title:"代码补全 (Tab)",description:"配置 Tab 键代码补全、建议与光标导航行为。"}'),
        ('{title:"Editor Settings",description:"Configure editor-specific behaviors and shortcuts."}',
         '{title:"编辑器设置",description:"配置编辑器特定行为与代码格式化偏好。"}'),
        ('{title:"Developer",description:"Developer-only tools. These settings are stored locally in this browser and do not affect other users."}',
         '{title:"开发者选项",description:"开发者专用高级工具。这些配置保存在本地，不会影响其他用户。"}'),
        ('{title:"Customizations",description:A.createElement("span",null,"Configure default behaviors, skills, and MCP servers."',
         '{title:"技能与自定义",description:A.createElement("span",null,"配置默认智能体行为、自定义技能 (Skills) 与 MCP 扩展服务。"'),

        # 10d. 外观与主题分项 (Appearance)
        ('title:"Light Theme"', 'title:"浅色主题配色"'),
        ('title:"Dark Theme"', 'title:"深色主题配色"'),
        ('label:"Theme",value:', 'label:"界面主题",value:'),
        ('case 2:F="Light";break a;case 3:F="Dark";break a;default:F=a?"Inherit Editor":"System"',
         'case 2:F="浅色模式 (Light)";break a;case 3:F="深色模式 (Dark)";break a;default:F=a?"跟随编辑器":"跟随系统"'),
        ('label:"Contrast",description:""', 'label:"色彩对比度",description:""'),
        ('title:"Marketplace"', 'title:"插件与扩展市场"'),
        ('label:"Advanced Settings"', 'label:"高级应用配置"'),
        ('title:"Default Customizations"', 'title:"默认内置能力"'),
        ('label:"Include Jetski Default Customizations",\ndescription:"Include default customizations, such as default skills."',
         'label:"包含内置默认能力与技能",\ndescription:"启用系统内置的通用技能与默认智能体配置。"'),
        ('title:"Token Usage"', 'title:"Token 资源用量"'),
        ('title:"Plugins"', 'title:"功能插件 (Plugins)"'),
        ('title:"Build With Google Plugins"', 'title:"官方推荐扩展插件"'),
        ('label:"Build With Google Plugins",\ndescription:"Browse and enable plugins from the Build With Google catalog."',
         'label:"官方推荐扩展插件",\ndescription:"浏览并启用官方插件库中的各类辅助工具。"'),
        ('title:"Hooks"', 'title:"生命周期钩子 (Hooks)"'),
        ('title:"Manage Hooks"', 'title:"管理钩子脚本"'),
        ('label:"Manage Hooks",description:"Configure hooks that run on agent lifecycle events."',
         'label:"管理钩子脚本",description:"配置在智能体各个执行生命周期自动触发的自定义脚本。"'),
        ('label:"Enable Telemetry"', 'label:"启用遥测数据上报"'),
        ('label:"Marketing Emails"', 'label:"产品营销邮件"'),
        ('title:"Sound"', 'title:"提示音效"'),
        ('title:"Recommended"', 'title:"常用推荐快捷键"'),
        ('title:"Layout Controls"', 'title:"界面布局快捷键"'),
        ('overrides:{label:"Open File Search"}', 'overrides:{label:"打开文件搜索"}'),
        ('overrides:{label:"Add to Chat/Quote"', 'overrides:{label:"添加到对话 / 引用"'),
        ('"Feature Environment Override"', '"特性环境覆盖模拟"'),
        ('label:"Override feature environment",description:"When enabled, the values below replace the auto-detected OS, host, binary, and user type used for feature gating."',
         'label:"覆盖运行环境特性",description:"启用后，以下模拟的系统类型、宿主环境与客户端信息将替代系统自动检测值。"'),
        ('label:"Operating System",description:"Simulate running on a different OS."',
         'label:"模拟操作系统",description:"模拟运行在不同的操作系统环境下 (如 Linux、macOS、Windows)。"'),
        ('label:"Host Environment",description:"Simulate a different host (Electron, desktop or mobile Web, Extension, remote control, or installed PWA).",\nrightElement:',
         'label:"模拟宿主运行环境",description:"模拟不同的宿主环境（桌面 Electron、浏览器或移动端）。",\nrightElement:'),
        ('label:"Binary",description:"Simulate running as a different binary (Hub or the IDE/editor).",rightElement:',
         'label:"模拟运行二进制版本",description:"模拟运行在独立 Hub 或嵌入式 IDE 环境下。",rightElement:'),
        ('"Custom Flags"', '"自定义功能实验开关 (Flags)"'),
        ('placeholder:"Search flags"', 'placeholder:"搜索实验开关..."'),
        ('''placeholder:"Turn on a flag you don't have"''', 'placeholder:"输入并开启新特性 Flag"'),

        # 10e. 设置项总注册表 (GM 选项的 Label 与 Description)
        ('label:"Allow List Terminal Commands",description:"The agent auto-executes commands matched by an allow list entry."',
         'label:"终端命令白名单",description:"智能体将自动执行与白名单匹配的终端命令，无需手动逐一确认。"'),
        ('label:"Agent Auto-Fix Lints",description:"Give the agent awareness of lint errors created by its edits so it can fix them without explicit prompting.",settingType:"switch"',
         'label:"智能体自动修复代码 Lint 错误",description:"赋予智能体感知代码编辑引发的 Lint 报错能力，并允许其自动尝试修复。",settingType:"switch"'),
        ('label:"Strict Mode",description:"Enforce settings that prevent the agent from autonomously running targeted exploits and require human review for all agent actions. Visit antigravity.google/docs/strict-mode for details.",settingType:"switch"',
         'label:"严格防护模式",description:"强制启用安全策略，阻止智能体自动查看或修改工作区目录之外的文件。访问 antigravity.google/docs/strict-mode 了解详情。",settingType:"switch"'),
        ('label:"Agent Non-Workspace File Access",description:"Allow the agent to automatically view and edit files outside the current workspace. Use with caution: this gives the agent access to additional potentially-relevant information, but also allows the agent',
         'label:"允许访问工作区外文件",description:"允许智能体在需要时自动读取或编辑当前工作区之外的文件。请谨慎使用：这会为智能体提供访问相关辅助信息的能力，但也会赋予其更广的文件系统访问权限。'),
        ('label:"Command Setup Script",description:"A shell setup script run before every command the agent executes."',
         'label:"命令前置初始化脚本",description:"在智能体执行每条终端命令前自动运行的 Shell 环境初始化脚本。"'),
        ('label:"Enable Terminal Sandbox",description:"Run terminal commands with sandbox restrictions."',
         'label:"启用终端沙箱隔离",description:"在沙箱隔离受限环境中安全运行终端命令。"'),
        ('label:"Sandbox Allow Network",description:"Allow sandboxed commands to make network requests."',
         'label:"沙箱命令允许网络访问",description:"允许在沙箱中运行的命令发起外部网络请求。"'),
        ('''label:"Enable Shell Integration",description:"Use the IDE's shell integration to detect and report terminal command execution. When disabled, the agent uses its own shell. Restart the application for this to take effect.",settingType:"switch"''',
         'label:"启用终端 Shell 集成",description:"使用 IDE 的终端 Shell 集成检测并报告命令执行状态。关闭后智能体将使用独立 Shell，重启应用后生效。",settingType:"switch"'),
        ('''label:"Review Policy",description:"Specifies the agent's behavior when asking for review on artifacts, which are documents it creates to enable a richer conversation experience."''',
         'label:"工件生成审查策略",description:"指定智能体在创建工件 (文档、方案等) 时是否需要用户审查确认。"'),
        ('label:"Enable Sounds for Agent",description:"Play a sound when the agent finishes generating a response."',
         'label:"智能体提示音效",description:"智能体完成思考与生成任务后播放提示音效。"'),
        ('label:"Enable Notifications for Agent",description:"Show browser notifications when your action is needed or execution finishes."',
         'label:"智能体系统通知",description:"当需要您确认操作或任务执行结束时，在状态栏或系统通知中推送提醒。"'),
        ('label:"Auto-Expand Changes Overview",description:"Automatically expand the Changes Overview toolbar when the agent finishes generating a response."',
         'label:"自动展开代码变更总览",description:"当智能体完成代码修改生成后，自动展开代码变更总览工具栏。"'),
        ('label:"Conversation History",description:"Let the agent access past conversations to inform its responses."',
         'label:"历史对话记忆检索",description:"允许智能体检索历史对话上下文以提供更精准连贯的解答。"'),
        ('label:"Auto-Open Edited Files",description:"Open files in the background if the agent creates or edits them"',
         'label:"自动在后台打开被编辑的文件",description:"当智能体新建或编辑文件时，自动在后台编辑器中打开对应文件。"'),
        ('label:"Open Agent on Reload",description:"Open the agent panel on window reload"',
         'label:"窗口重载时自动打开智能体",description:"当刷新或重新载入窗口时，默认展开智能体对话面板。"'),
        ('label:"Verbose Agent Chat",description:"Display and preserve intermediate thinking steps."',
         'label:"完整展示思考过程",description:"在对话中完整展示并保留智能体的思考推理过程与中间步骤。"'),
        ('label:"Custom Context Menus",description:"Replace the default browser right-click menu with quick actions."',
         'label:"自定义右键菜单",description:"将默认的浏览器右键菜单替换为快捷操作菜单。"'),
        ('label:"Conversation Width",description:"Configure the maximum width of the conversation panel."',
         'label:"对话面板宽度",description:"配置对话视图的最大显示宽度。"'),
        ('case 2:return"Narrow";case 3:return"Wide";default:return"Default"',
         'case 2:return"紧凑窄屏";case 3:return"宽屏模式";default:return"默认宽度"'),
        ('label:"Markdown Artifact Width",description:"Configure the default width of markdown artifacts."',
         'label:"工件预览宽度",description:"配置 Markdown 文档工件预览的显示宽度。"'),
        ('case 2:return"Wide";case 3:return"Fill";default:return"Default"',
         'case 2:return"宽屏";case 3:return"全屏撑满";default:return"默认宽度"'),
        ('label:"Suggestions in Editor",description:"Show suggestions when typing in the editor"',
         'label:"编辑器代码实时补全",description:"在编辑器中键入代码时实时显示智能补全建议。"'),
        ('label:"Tab to Jump",description:"Predict the location of your next edit and navigate you there with a tab keypress."',
         'label:"Tab 键智能光标跳转",description:"智能预测您下一处需要修改的位置，按 Tab 键即可一键跳转光标。"'),
        ('label:"Tab to Import",description:"Quickly add and update imports with a tab keypress."',
         'label:"Tab 键快速导入模块",description:"按 Tab 键快速自动添加和更新缺失的依赖导入语句。"'),
        ('label:"Tab Speed",description:"Set the speed of tab suggestions"',
         'label:"补全响应速度",description:"设置 Tab 键代码建议的生成与展示响应速度。"'),
        ('case I.AutocompleteSpeed.FAST:return"Fast";case I.AutocompleteSpeed.SLOW:return"Slow";default:return"Fast"',
         'case I.AutocompleteSpeed.FAST:return"极速 (Fast)";case I.AutocompleteSpeed.SLOW:return"标准 (Slow)";default:return"极速 (Fast)"'),
        ('label:"Highlight After Accept",description:"Highlight newly inserted text after accepting a Tab completion."',
         'label:"采纳后高亮提示",description:"采纳 Tab 补全建议后，短暂高亮显示新插入的代码片段。"'),
        ('label:"Tab Gitignore Access",description:"Allow Tab to view and edit the files in .gitignore. Use with caution if your .gitignore lists files containing credentials, secrets, or other sensitive information."',
         'label:"允许补全访问 .gitignore 文件",description:"允许 Tab 补全功能读取并修改 .gitignore 中的文件。若忽略文件中包含敏感凭据，请谨慎开启。"'),
        ('label:"Enable Browser Tools",description:"Let the agent use browser tools to open URLs, read web pages, and interact with browser content. This gives the agent access to important (and often critical) knowledge and methods of validation, but any browser integration does increase exposure to external malicious parties for security exploits."',
         'label:"启用智能体浏览器工具",description:"允许智能体调用浏览器打开网址、阅读网页并与网页内容交互，便于智能体获取最新知识与测试验证。"'),
        ('label:"Browser Javascript Execution Policy",description:"Controls whether the agent can run custom JavaScript to automate complex browser actions."',
         'label:"浏览器脚本执行权限",description:"控制智能体是否可以在自动化浏览器操作中运行自定义 JavaScript 脚本。"'),
        ("""label:"Show Selection Actions",description:'Show "Edit" and "Chat" buttons when selecting text in the editor.'""",
         """label:"代码选中快捷操作浮标",description:'在编辑器中选中代码时浮动显示“编辑”与“提问”快捷按钮。'"""),
        ('label:"Include Jetski Default Customizations",\ndescription:"Include default customizations, such as default skills."',
         'label:"包含内置默认能力与技能",\ndescription:"启用系统内置的通用技能与默认智能体配置。"'),
        ('label:"Prevent Sleep",description:"Prevent the computer from sleeping while the app is running."',
         'label:"防止设备休眠",description:"应用在前台运行时阻止系统进入休眠状态。"'),
        ('label:"Keep In Menu Bar",description:"Keep the app accessible from the menu bar and running in the background when all windows are closed."',
         'label:"保持后台静默运行",description:"关闭窗口后应用继续在后台驻留运行。"'),
        ('label:"Automatic Check for Updates",description:"Automatically prompt you to restart the app when a new update is available. When disabled, you can check for updates manually from the app menu.",settingType:"switch"}',
         'label:"自动检查版本更新",description:"发现新版本时自动提示重启更新；关闭后需通过菜单手动检查更新。",settingType:"switch"}'),
        ('label:"Enable Remote Control",description:"Manage your conversations from the companion website."',
         'label:"启用远程协同控制",description:"支持在其他设备或配套网页端远程管理与协同对话。"'),
        ('label:"Nickname",description:"A nickname for identifying this application in the companion website. Changing this will restart the connection."',
         'label:"设备别名 / 昵称",description:"用于在远程管理端标识此设备的自定义名称。修改后将重启连接。"'),
        ('label:"Inline Actions",description:"Show a floating notification card when background conversations need your input. Answer questions, approve commands, and grant permissions without leaving your current conversation. Share feedback at go/inline-actions-feedback."',
         'label:"浮动通知动作卡片",description:"当后台任务需要您确认操作时弹出浮动卡片，无需切换对话即可快速作答或审批。"'),
        ('label:"Autonomous Mode",description:"Adds an Autonomous Mode switch to the modes dropdown below the input box. Turns sent with it on run non-interactively: the agent does not ask questions or request new permissions."',
         'label:"全自主模式 (Autonomous Mode)",description:"在输入框下方添加自主模式开关。开启后智能体将全程自主执行，不向用户提问或申请权限。"'),

        # 10f. 全局命令面板与快捷键映射 (Jj)
        ('{id:"toggleBottomPane",label:"Toggle Terminal"', '{id:"toggleBottomPane",label:"打开/关闭终端"'),
        ('{id:"toggleFileViewer",label:"Toggle File Viewer"', '{id:"toggleFileViewer",label:"打开/关闭文件查看器"'),
        ('{id:"toggleEditor",label:"Toggle Editor"', '{id:"toggleEditor",label:"打开/关闭编辑器"'),
        ('{id:"createSplitTerminal",label:"Split Terminal"', '{id:"createSplitTerminal",label:"拆分终端窗口"'),
        ('{id:"closeTerminalTab",label:"Close Terminal Tab"', '{id:"closeTerminalTab",label:"关闭终端标签页"'),
        ('{id:"openNewTerminalTab",label:"New Terminal Tab"', '{id:"openNewTerminalTab",label:"新建终端标签页"'),
        ('{id:"openNewAuxTab",label:"New Tab"', '{id:"openNewAuxTab",label:"新建标签页"'),
        ('{id:"openCommandPalette",label:"File Picker"', '{id:"openCommandPalette",label:"快速查找文件"'),
        ('{id:"openCommandPaletteWithPrefix",label:"Open Command Palette"', '{id:"openCommandPaletteWithPrefix",label:"打开命令面板"'),
        ('{id:"openShortcutsOverlay",\nlabel:"Open Keyboard Shortcuts"', '{id:"openShortcutsOverlay",\nlabel:"打开快捷键列表"'),
        ('openConversationHistory:{id:"openConversationHistory",label:"Open Conversation History",\nicon:"history",keybindings:{binding:{mod:!0,key:"y"}}}',
         'openConversationHistory:{id:"openConversationHistory",label:"打开对话历史",\nicon:"history",keybindings:{binding:{mod:!0,key:"y"}}}'),
        ('{id:"openScheduledTasks",label:"Scheduled Tasks"', '{id:"openScheduledTasks",label:"定时任务"'),
        ('{id:"vcs",label:"Open Commit Graph"', '{id:"vcs",label:"打开 Git 提交历史图谱"'),
        ('{id:"codeSearch",label:"Code Search"', '{id:"codeSearch",label:"全局代码搜索"'),
        ('{id:"mentionSelection",label:"Add to Chat"', '{id:"mentionSelection",label:"添加到对话"'),
        ('{id:"insertMentionSelection",label:"Add to Chat"', '{id:"insertMentionSelection",label:"添加到对话"'),
        ('{id:"insertQuoteSelection",label:"Quote Selection"', '{id:"insertQuoteSelection",label:"引用选中文本"'),
        ('{id:"insertCodeSearchSelection",label:"Open in Code Search"', '{id:"insertCodeSearchSelection",label:"在代码搜索中打开"'),
        ('{id:"artifactStartComment",label:"Comment on Selection"', '{id:"artifactStartComment",label:"对选中内容添加批注"'),
        ('{id:"focusInput",label:"Focus Input"', '{id:"focusInput",label:"聚焦到输入框"'),
        ('{id:"zoomIn",label:"Zoom In"', '{id:"zoomIn",label:"放大界面"'),
        ('{id:"zoomOut",label:"Zoom Out"', '{id:"zoomOut",label:"缩小界面"'),
        ('{id:"zoomReset",label:"Reset Zoom"', '{id:"zoomReset",label:"重置缩放"'),
        ('{id:"findInPane",label:"Find in Pane"', '{id:"findInPane",label:"在当前面板中查找"'),
        ('{id:"goBack",label:"Go Back"', '{id:"goBack",label:"返回上一页"'),
        ('{id:"goForward",label:"Go Forward"', '{id:"goForward",label:"前进下一页"'),
        ('{id:"goBackInAuxPane",label:"Go Back in Pane"', '{id:"goBackInAuxPane",label:"辅助面板返回"'),
        ('{id:"goForwardInAuxPane",label:"Go Forward in Pane"', '{id:"goForwardInAuxPane",label:"辅助面板前进"'),
        ('{id:"downloadDiagnostics",label:"Download Diagnostics"', '{id:"downloadDiagnostics",label:"导出系统诊断日志"'),
        ('{id:"toggleTheme",label:"Toggle Between Light/Dark Themes"', '{id:"toggleTheme",label:"切换浅色/深色主题"'),

        # 10g. 文件管理与目录操作 (Explorer / Files)
        ('function Yta(){switch(qq()){case "macos":return"Reveal in Finder";case "windows":return"Show in File Explorer";case "linux":return"Show in File Manager";default:return"Show in File Explorer"}}',
         'function Yta(){return"在系统文件管理器中显示"}'),
        ('{type:"label",label:"Recent files"}', '{type:"label",label:"最近访问的文件"}'),

        # 10h. Git 源码版本控制与代码变更总览 (Changes Overview)
        ('switch(a){case "workingDirectory":case "battleManifest":return"Changes";case "agentEdits":return"Agent Edits";case "staged":return"Staged Changes";case "branch":return"Branch Changes";default:return a.length>=7?`Commit ${a.slice(0,7)}`:a}',
         'switch(a){case "workingDirectory":case "battleManifest":return"工作区更改";case "agentEdits":return"智能体修改";case "staged":return"已暂存更改";case "branch":return"分支更改";default:return a.length>=7?`提交 ${a.slice(0,7)}`:a}'),
        ('f=e?"Amend staged changes into the current commit":"Stage and amend all changes into the current commit";return[{key:"git-commit",label:"Commit",tooltip:e?"Commit staged changes":"Stage and commit all changes"',
         'f=e?"追加已暂存的更改到当前提交":"暂存并追加所有更改到当前提交";return[{key:"git-commit",label:"提交",tooltip:e?"提交已暂存的更改":"暂存并提交所有更改"'),
        ('{key:"git-amend",label:"Amend"', '{key:"git-amend",label:"追加提交 (Amend)"'),
        ('{key:"git-push",label:"Push"', '{key:"git-push",label:"推送 (Push)"'),
        ('var x=l("Committing...")', 'var x=l("正在提交...")'),
        ('E=l("Generating commit message...","generate-commit-message")', 'E=l("正在生成提交说明...","generate-commit-message")'),
        ('{message:gp(F),title:"Failed to Generate Commit Message"}', '{message:gp(F),title:"生成提交说明失败"}'),
        ('{title:"Commit succeeded",message:y?`Committed to ${y}.`:""}', '{title:"提交成功",message:y?`已成功提交至 ${y}。`:""}'),
        ('{message:gp(D),title:"Failed to Commit"}', '{message:gp(D),title:"提交失败"}'),
        ('let q=l("Amending...")', 'let q=l("正在追加提交...")'),
        ('{message:gp(r),title:"Failed to Amend"}', '{message:gp(r),title:"追加提交失败"}'),
        ('let v=l("Pushing...")', 'let v=l("正在推送...")'),
        ('{title:"Push succeeded",message:', '{title:"推送成功",message:'),
        ('{message:gp(w),title:"Failed to Push",telemetry:', '{message:gp(w),title:"推送失败",telemetry:'),
        ('tooltip:"Unstage change"', 'tooltip:"取消暂存更改"'),
        ('tooltip:"Stage change"', 'tooltip:"暂存此更改"'),
        ('{key:"discard",label:"Discard",icon:"undo",tooltip:"Discard unstaged changes"',
         '{key:"discard",label:"放弃更改",icon:"undo",tooltip:"放弃未暂存的更改"'),
        ('label:"Include unstaged changes"', 'label:"同时包含未暂存的更改"'),
        ('b?{char:"A",title:"Added (Staged)",colorClass:"text-green-500 font-bold"}:{char:"U",title:"Untracked (Unstaged)",colorClass:"text-green-500 font-bold"}',
         'b?{char:"A",title:"新增 (已暂存)",colorClass:"text-green-500 font-bold"}:{char:"U",title:"未跟踪 (未暂存)",colorClass:"text-green-500 font-bold"}'),
        ('case 2:return{char:"M",title:"Modified",colorClass:"text-yellow-500 font-bold"}',
         'case 2:return{char:"M",title:"已修改",colorClass:"text-yellow-500 font-bold"}'),
        ('case 3:return{char:"D",title:"Deleted",colorClass:"text-red-500 font-bold"}',
         'case 3:return{char:"D",title:"已删除",colorClass:"text-red-500 font-bold"}'),
        ('case 4:return{char:"R",title:"Renamed",colorClass:"text-blue-500 font-bold"}',
         'case 4:return{char:"R",title:"已重命名",colorClass:"text-blue-500 font-bold"}'),
        ('case 5:return{char:"C",title:"Copied",colorClass:"text-blue-500 font-bold"}',
         'case 5:return{char:"C",title:"已复制",colorClass:"text-blue-500 font-bold"}'),

        # 10i. 设置中心深层小标题、卡片说明、下拉选项与操作按钮 (Deep Settings Polish)
        ('["Settings",Geb(a)]', '["设置",Geb(a)]'),
        ('A.createElement(hNb,{text:"Settings"})', 'A.createElement(hNb,{text:"设置"})'),
        ('A.createElement(hNb,{text:"Workspaces"})', 'A.createElement(hNb,{text:"工作区"})'),
        ('["Workspaces",nr(b)]', '["工作区",nr(b)]'),
        ('["Projects",f]', '["项目",f]'),
        ('["Not in Project","Conversations"]', '["未加入项目","对话列表"]'),

        ('{title:"Execution",settings:[Ui.QUEUED_MESSAGE_DELIVERY_STRATEGY]}', '{title:"执行控制",settings:[Ui.QUEUED_MESSAGE_DELIVERY_STRATEGY]}'),
        ('{title:"Chat Settings",settings:[Ui.THEME_MODE,Ui.VERBOSE_AGENT_CHAT,Ui.CONVERSATION_WIDTH,Ui.ARTIFACT_WIDTH]}', '{title:"对话界面设置",settings:[Ui.THEME_MODE,Ui.VERBOSE_AGENT_CHAT,Ui.CONVERSATION_WIDTH,Ui.ARTIFACT_WIDTH]}'),
        ('{title:"Context Menus",settings:[Ui.CUSTOM_CONTEXT_MENUS_ENABLED]}', '{title:"右键快捷菜单",settings:[Ui.CUSTOM_CONTEXT_MENUS_ENABLED]}'),
        ('{title:"Suggestions",settings:[Ui.TAB_ENABLED,Ui.AUTOCOMPLETE_SPEED,Ui.DISABLE_HIGHLIGHT_AFTER_ACCEPT,\nUi.DISABLE_TAB_TO_IMPORT]}', '{title:"代码建议与提示",settings:[Ui.TAB_ENABLED,Ui.AUTOCOMPLETE_SPEED,Ui.DISABLE_HIGHLIGHT_AFTER_ACCEPT,\nUi.DISABLE_TAB_TO_IMPORT]}'),
        ('{title:"Navigation",settings:[Ui.TAB_TO_JUMP]}', '{title:"智能跳转导航",settings:[Ui.TAB_TO_JUMP]}'),
        ('{title:"Context",settings:[Ui.ALLOW_TAB_ACCESS_GITIGNORE_FILES]}', '{title:"上下文感知",settings:[Ui.ALLOW_TAB_ACCESS_GITIGNORE_FILES]}'),
        ('{title:"Default Customizations",settings:[Ui.INCLUDE_JETSKI_DEFAULT_CUSTOMIZATIONS]}', '{title:"默认内置能力",settings:[Ui.INCLUDE_JETSKI_DEFAULT_CUSTOMIZATIONS]}'),
        ('{title:"Customize Global Skills",settings:[Wi.SKILLS]}', '{title:"自定义全局技能",settings:[Wi.SKILLS]}'),
        ('{title:"Custom Agents",settings:[Wi.CUSTOM_AGENTS]}', '{title:"自定义智能体",settings:[Wi.CUSTOM_AGENTS]}'),
        ('{title:"MCP Servers",settings:[Wi.MCP]}', '{title:"MCP 扩展服务",settings:[Wi.MCP]}'),
        ('{title:"Updater",settings:[Yi.AUTO_CHECK_FOR_UPDATES]}', '{title:"版本更新",settings:[Yi.AUTO_CHECK_FOR_UPDATES]}'),

        ('title:U?"Global Permissions":"Agent Settings"', 'title:U?"全局权限控制":"智能体权限设置"'),
        ('A.createElement(w3,{title:"Agent Behavior"}', 'A.createElement(w3,{title:"智能体行为"}'),
        ('A.createElement(w3,{title:"Terminal & Tooling Permissions"}', 'A.createElement(w3,{title:"终端与工具权限"}'),
        ('A.createElement(w3,{title:"Permission Details"}', 'A.createElement(w3,{title:"权限详细信息"}'),
        ('A.createElement(w3,{title:"Permission Settings"', 'A.createElement(w3,{title:"权限设置"'),
        ('A.createElement(w3,{title:"Local Permissions"', 'A.createElement(w3,{title:"本地工作区权限"'),
        ('A.createElement(w3,{title:"Workspace Command Access"}', 'A.createElement(w3,{title:"工作区命令访问权限"}'),
        ('A.createElement(w3,{title:"Workspace Web Access"}', 'A.createElement(w3,{title:"工作区网络访问权限"}'),
        ('A.createElement(w3,{title:"GitHub Policies"', 'A.createElement(w3,{title:"GitHub 策略"'),
        ('A.createElement(w3,{title:"Selection Actions"}', 'A.createElement(w3,{title:"选中文本操作"}'),

        ('[Ui.QUEUED_MESSAGE_DELIVERY_STRATEGY,{isProviderSetting:!0,screen:"General",label:"Queued Messages",description:"Configure when follow-up messages are sent."',
         '[Ui.QUEUED_MESSAGE_DELIVERY_STRATEGY,{isProviderSetting:!0,screen:"General",label:"排队消息发送时机",description:"配置智能体后续跟进消息是在空闲时排队发送还是立即发送。"'),
        ('case T.MessageDeliveryStrategy.NEXT_INVOCATION:return"Send Immediately";\ndefault:return"Queue"',
         'case T.MessageDeliveryStrategy.NEXT_INVOCATION:return"立即发送";\ndefault:return"排队等待"'),
        ('case T.MessageDeliveryStrategy.NEXT_INVOCATION:return"Interrupt the agent and send immediately.";default:return"Queue until after the current turn."',
         'case T.MessageDeliveryStrategy.NEXT_INVOCATION:return"打断智能体当前响应并立即发送。";default:return"排队等待当前轮次结束后发送。"'),
        ('A.createElement("span",null,"Keyboard shortcuts")', 'A.createElement("span",null,"快捷键说明")'),
        ('Queues after the turn', '当前轮次结束后排队发送'),
        ('Sends immediately', '立即发送消息'),
        ('On empty prompt, sends next in queue', '输入框为空时，发送队列中的下一条消息'),

        ('label:"Security Preset",description:lb', 'label:"安全预设方案",description:lb'),
        ('"Controls the actions the agent can take."', '"控制智能体可以执行的操作权限级别。"'),
        ('Ia==="use_global"?\n"Inherit Global":Ia==="custom"?"Custom"', 'Ia==="use_global"?\n"继承全局设置":Ia==="custom"?"自定义"'),
        ('Ia==="use_global"?"Inherits your Global Permissions when working in this project.":Ia==="custom"?"Manually customize individual settings."',
         'Ia==="use_global"?"在此项目中继承您的全局权限设置。":Ia==="custom"?"手动自定义各项详细权限。"'),
        ('displayResolver:Bb=>Bb==="use_global"?"Inherit Global":Bb==="custom"?"Custom":Mt[ta][Bb]?.displayName??"Custom"',
         'displayResolver:Bb=>Bb==="use_global"?"继承全局设置":Bb==="custom"?"自定义":Mt[ta][Bb]?.displayName??"自定义"'),
        ('resolveOptionToDescription:Bb=>Bb==="use_global"?"Inherits your Global Permissions when working in this project.":Bb==="custom"?"Manually customize individual settings."',
         'resolveOptionToDescription:Bb=>Bb==="use_global"?"在此项目中继承您的全局权限设置。":Bb==="custom"?"手动自定义各项详细权限。"'),

        ('label:"Outside of folders file access policy",description:"Configures how the agent tries to access files outside of its working folders."',
         'label:"工作区外文件访问策略",description:"配置智能体尝试访问工作区以外的文件时的行为规则。"'),
        ('Qb===I.AgentSettingPolicy.UNSPECIFIED?"Inherit Global":Qb===I.AgentSettingPolicy.ALLOW?"Allow":Qb===I.AgentSettingPolicy.DENY?"Deny":"Always Ask"',
         'Qb===I.AgentSettingPolicy.UNSPECIFIED?"继承全局设置":Qb===I.AgentSettingPolicy.ALLOW?"允许访问":Qb===I.AgentSettingPolicy.DENY?"禁止访问":"总是询问"'),
        ('displayResolver:Bb=>Bb===I.AgentSettingPolicy.UNSPECIFIED?"Inherit Global":Bb===I.AgentSettingPolicy.ALLOW?\n"Allow":Bb===I.AgentSettingPolicy.DENY?"Deny":"Always Ask"',
         'displayResolver:Bb=>Bb===I.AgentSettingPolicy.UNSPECIFIED?"继承全局设置":Bb===I.AgentSettingPolicy.ALLOW?\n"允许访问":Bb===I.AgentSettingPolicy.DENY?"禁止访问":"总是询问"'),

        ('label:"Terminal Command Auto Execution",description:"Controls whether terminal commands require your approval before running."',
         'label:"终端命令自动执行策略",description:"控制智能体执行终端命令前是否必须经过您的审批。"'),
        ('displayResolver:Bb=>Bb===I.CascadeCommandsAutoExecution.UNSPECIFIED?"Inherit Global":Bb===I.CascadeCommandsAutoExecution.EAGER?\n"Always Proceed":Bb===I.CascadeCommandsAutoExecution.PROCEED_IN_SANDBOX?"Proceed in Sandbox":"Require Review"',
         'displayResolver:Bb=>Bb===I.CascadeCommandsAutoExecution.UNSPECIFIED?"继承全局设置":Bb===I.CascadeCommandsAutoExecution.EAGER?\n"总是自动执行":Bb===I.CascadeCommandsAutoExecution.PROCEED_IN_SANDBOX?"在沙箱中自动执行":"需要人工审批"'),
        ('function T1a(a){switch(a){case I.CascadeCommandsAutoExecution.EAGER:return"Always Proceed";case I.CascadeCommandsAutoExecution.AUTO:return"Auto";case I.CascadeCommandsAutoExecution.OFF:return"Require Review";default:return"Proceed in Sandbox"}}',
         'function T1a(a){switch(a){case I.CascadeCommandsAutoExecution.EAGER:return"总是自动执行";case I.CascadeCommandsAutoExecution.AUTO:return"自动智能判断";case I.CascadeCommandsAutoExecution.OFF:return"需要人工审批";default:return"在沙箱中自动执行"}}'),

        ('label:"Enable Sandbox Mode (Preview)",\ndescription:"Restricts agent tools to a secure, isolated local sandbox."',
         'label:"启用沙箱隔离模式 (预览版)",\ndescription:"将智能体工具限制在安全隔离的本地沙箱环境中运行。"'),
        ('Ra===void 0?"Inherit Global":Ra?"Enabled":"Disabled"', 'Ra===void 0?"继承全局设置":Ra?"已启用":"已禁用"'),

        ('Ki=H?"Modify permissions for file, terminal, and MCP tools.":"Modify permissions for file and terminal tools."',
         'Ki=H?"修改文件、终端以及 MCP 工具的调用权限。":"修改文件与终端工具的调用权限。"'),
        ('rightElement:A.createElement(tA,{variant:"secondary",size:"md",onClick:()=>{Aa("tools")}},"Open")',
         'rightElement:A.createElement(tA,{variant:"secondary",size:"md",onClick:()=>{Aa("tools")}},"打开")'),
        ('rightElement:A.createElement(tA,{variant:"secondary",size:"sm",onClick:()=>{Aa("github")}},"Open")',
         'rightElement:A.createElement(tA,{variant:"secondary",size:"sm",onClick:()=>{Aa("github")}},"打开")'),

        ('label:"Read Files",description:"Paths the agent can read inside this workspace."',
         'label:"读取文件权限",description:"智能体在此工作区中可读取的文件路径。"'),
        ('label:"Write Files",description:"Paths the agent can modify inside this workspace."',
         'label:"写入文件权限",description:"智能体在此工作区中可修改的文件路径。"'),
        ('label:"Terminal Commands",description:"Terminal commands the agent can execute in this workspace."',
         'label:"终端命令权限",description:"智能体在此工作区中可执行的终端命令。"'),
        ('label:"Commands Outside Sandbox",description:"Commands the agent can run outside the sandbox in this workspace."',
         'label:"沙箱外命令权限",description:"智能体在此工作区中可在沙箱隔离外直接运行的命令。"'),
        ('label:"MCP Tools",description:"External tools the agent can call via Model Context Protocol."',
         'label:"MCP 扩展工具权限",description:"智能体可通过模型上下文协议 (MCP) 调用的外部工具。"'),
        ('label:"Read URLs",description:"URLs the agent can read or open in this workspace."',
         'label:"读取 URL 权限",description:"智能体在此工作区中可读取或在浏览器中打开的网页网址。"'),
        ('execute_url",label:"Execute URLs",\ndescription:"URLs the agent can actuate on in this workspace."',
         'execute_url",label:"执行 URL 权限",\ndescription:"智能体在此工作区中可进行交互操作的网页网址。"'),
        ('label:"File Access Rules",badge:pa>0?pa:void 0,description:"Configure allowed and denied paths for file reads and writes."',
         'label:"文件访问规则",badge:pa>0?pa:void 0,description:"配置允许和禁止读取与写入的文件路径规则。"'),
        ('label:"Network Access Rules",badge:ia>0?ia:void 0,description:"Configure allowed and denied URLs for reading."',
         'label:"网络访问规则",badge:ia>0?ia:void 0,description:"配置允许和禁止读取的网页 URL 规则。"'),
        ('label:"Browser Actuation Rules",description:"Configure allowed and denied URLs for browser actuation."',
         'label:"浏览器操作规则",description:"配置允许和禁止进行自动化交互的网页 URL 规则。"'),

        ('label:"Always Proceed",description:"Agent never asks for review. This maximizes the autonomy of the Agent, but also has the highest risk of the Agent operating over unsafe or injected Artifact content."',
         'label:"总是自动放行",description:"智能体从不请求人工审查工件。这能最大化自动化效率，但也会增加处理不安全内容的风险。"'),
        ('label:"Always Ask",description:"Agent always asks for review."',
         'label:"总是询问确认",description:"智能体在生成或更新工件时总是请求人工审查确认。"'),

        ('case I.BrowserJsExecutionPolicy.DISABLED:return"Disabled";case I.BrowserJsExecutionPolicy.ALWAYS_ASK:return"Request Review";\ncase I.BrowserJsExecutionPolicy.TURBO:return"Always Proceed";default:return"Request Review"',
         'case I.BrowserJsExecutionPolicy.DISABLED:return"禁止执行";case I.BrowserJsExecutionPolicy.ALWAYS_ASK:return"需要人工审批";\ncase I.BrowserJsExecutionPolicy.TURBO:return"总是自动允许";default:return"需要人工审批"'),
        ('cutionPolicy.DISABLED:return"Block all browser JavaScript execution.";case I.BrowserJsExecutionPolicy.ALWAYS_ASK:return"Prompt for approval before running browser scripts.";case I.BrowserJsExecutionPolicy.TURBO:return"Allow full browser script execution without prompting.";default:return"Prompt for approval before running browser scripts."',
         'cutionPolicy.DISABLED:return"禁止所有浏览器 JavaScript 脚本执行。";case I.BrowserJsExecutionPolicy.ALWAYS_ASK:return"在执行浏览器脚本前提示您进行确认与审批。";case I.BrowserJsExecutionPolicy.TURBO:return"无需提示直接允许完整的浏览器脚本自动执行。";default:return"在执行浏览器脚本前提示您进行确认与审批。"'),

        ('case I.AutocompleteSpeed.FAST:return"Fast";case I.AutocompleteSpeed.SLOW:return"Slow";default:return"Fast"',
         'case I.AutocompleteSpeed.FAST:return"快速响应";case I.AutocompleteSpeed.SLOW:return"平稳响应";default:return"快速响应"'),

        ('screen:"App",label:"Automatic Check for Updates",description:"Automatically prompt you to restart the app when a new update is available. When disabled, you can check for',
         'screen:"App",label:"自动检查版本更新",description:"有新版本可用时自动提示您重启应用以完成更新。关闭后，您可以手动检查'),

        ('Za==="use_global"?"Inherit Global":Za==="custom"?\n"Custom":Mt[ta][Za]?.displayName??"Custom"',
         'Za==="use_global"?"继承全局设置":Za==="custom"?\n"自定义":Mt[ta][Za]?.displayName??"自定义"'),
        ('displayName:"Default",shortDisplayName:"Default",shortDescription:"Requires manual review for all terminal commands and file accesses outside of the working folders."',
         'displayName:"默认安全模式",shortDisplayName:"默认",shortDescription:"在执行终端命令或访问工作区外的文件前均需人工审批。"'),
        ('displayName:"Turbo mode",shortDisplayName:"Turbo",shortDescription:"Disables all safety barriers for maximal iteration velocity."',
         'displayName:"极速模式 (Turbo)",shortDisplayName:"极速",shortDescription:"解除所有安全限制以获得最高迭代执行速度。"'),
        ('a==="use_global"?"Inherit Global":a==="turbo"?"Always Proceed":"Always Ask"',
         'a==="use_global"?"继承全局设置":a==="turbo"?"总是自动放行":"总是询问确认"'),
        ('Bb==="use_global"?"Inherit Global":Bb==="turbo"?"Always Proceed":"Always Ask"',
         'Bb==="use_global"?"继承全局设置":Bb==="turbo"?"总是自动放行":"总是询问确认"'),
        ('Bb===void 0?"Inherit Global":Bb===!0?"Enabled":"Disabled"',
         'Bb===void 0?"继承全局设置":Bb===!0?"已启用":"已禁用"'),
        ('qb===I.CascadeCommandsAutoExecution.UNSPECIFIED?\n"Inherit Global":T1a(qb)',
         'qb===I.CascadeCommandsAutoExecution.UNSPECIFIED?\n"继承全局设置":T1a(qb)'),
        ('case I.CascadeCommandsAutoExecution.OFF:return"Request Review";default:return"Proceed in Sandbox"',
         'case I.CascadeCommandsAutoExecution.OFF:return"需要人工审批";default:return"在沙箱中自动执行"'),
        ('A.createElement("span",{className:"opacity-50"},"Custom")',
         'A.createElement("span",{className:"opacity-50"},"自定义")'),

        # 10j. 模型用量、外观主题、权限控制与自定义项全盘补全 (All 5 Screens Deep Localization)
        ('A.createElement("span",null,"Models & Usage")', 'A.createElement("span",null,"模型与额度用量")'),
        ('description:"Manage your model quota and credits."', 'description:"管理您的模型配额与积分额度。"'),
        ('title:"Refresh quota and credits data","aria-label":"Refresh quota and credits data"',
         'title:"刷新模型配额与积分数据","aria-label":"刷新模型配额与积分数据"'),
        ('l==="signedIn"&&n&&A.createElement(w3,{title:"Plan"}',
         'l==="signedIn"&&n&&A.createElement(w3,{title:"当前套餐计划"}'),
        ('A.createElement("div",{className:"text-sm font-medium"},"Your Plan: ",n)',
         'A.createElement("div",{className:"text-sm font-medium"},"当前套餐: ",n)'),
        ('c.userTier.upgradeButtonText||"Upgrade"', 'c.userTier.upgradeButtonText||"升级套餐"'),
        ('label:"Enable AI Credit Overages",description:`When toggled on, ${h} will use your AI credits to fulfill model requests once you\'re out of model quota. ${h} will always use your model quota first before using AI credits.`',
         'label:"允许超额使用 AI 积分",description:`开启后，当您的模型配额用尽时，${h} 将自动使用您的 AI 积分继续处理模型请求。${h} 将始终优先消耗免费模型配额，配额不足时才会使用 AI 积分。`'),
        ('function ELb({group:a,sharedModels:b}){',
         'function ELb({group:a,sharedModels:b}){var _gName=a.displayName;if(_gName==="Gemini Models")_gName="Gemini 系列模型";else if(_gName==="Claude and GPT models")_gName="Claude 与 GPT 系列模型";else if(_gName==="Gemini 4 Argon")_gName="Gemini 4 Argon 模型";'),
        ('A.createElement("span",null,a.displayName)', 'A.createElement("span",null,_gName||a.displayName)'),
        ('function DLb({label:a,remainingFraction:b,refreshText:c,disabled:e}){',
         'function DLb({label:a,remainingFraction:b,refreshText:c,disabled:e}){if(typeof a==="string"){a=a.replace("Weekly Limit Remaining","每周剩余额度").replace("Five Hour Limit Remaining","5 小时周期剩余额度").replace("Gemini 4 Argon Weekly Limit","Gemini 4 Argon 每周剩余额度").replace("Weekly Limit","每周额度上限").replace("Limit Remaining","剩余额度");}if(typeof c==="string"){c=c.replace(/You have used some of your weekly limit, it will fully refresh in (\\d+) hours?, (\\d+) minutes?\\./,"您已消耗部分每周额度，将在 $1 小时 $2 分钟后完全重置。").replace(/You have used some of your weekly limit, it will fully refresh in (\\d+) hours?\\./,"您已消耗部分每周额度，将在 $1 小时后完全重置。").replace(/You have used some of your weekly limit, it will fully refresh in (\\d+) minutes?\\./,"您已消耗部分每周额度，将在 $1 分钟后完全重置。").replace(/You have used some of your 5-hour limit, it will fully refresh in (\\d+) hours?, (\\d+) minutes?\\./,"您已消耗部分 5 小时周期额度，将在 $1 小时 $2 分钟后完全重置。").replace(/You have used some of your 5-hour limit, it will fully refresh in (\\d+) minutes?\\./,"您已消耗部分 5 小时周期额度，将在 $1 分钟后完全重置。").replace("You have used some of your weekly limit","您已消耗部分每周额度").replace("You have used some of your 5-hour limit","您已消耗部分 5 小时周期额度");}'),
        ('var n=c&&c.userTier?.description,q=c?.userTier?.upgradeSubscriptionText||"";',
         'var n=c&&c.userTier?.description,q=c?.userTier?.upgradeSubscriptionText||"";if(q&&q.includes("upgrade to a Google AI Ultra"))q="您可以升级至 Google AI Ultra 套餐以获取更高的调用速率与额度。";'),

        ('A.createElement(w3,{title:"Appearance"}', 'A.createElement(w3,{title:"外观设置"}'),
        ('A.createElement(v3,{label:"Desktop Mode",description:"Use desktop viewport and user agent for the workspace"',
         'A.createElement(v3,{label:"桌面端工作区模式",description:"在工作区中使用桌面端视图比例与浏览器标识 (User-Agent)"'),
        ('Nrc=a=>{switch(a){case 2:return"Strong";default:return"Default"}}',
         'Nrc=a=>{switch(a){case 2:return"高对比度";default:return"默认对比度"}}'),
        ('A.createElement(v3,{label:"Preset",rightElement:', 'A.createElement(v3,{label:"配色预设",rightElement:'),
        ('A.createElement(ty,{id:c,content:"Reset to preset",place:"top"})',
         'A.createElement(ty,{id:c,content:"重置为预设配色",place:"top"})'),
        ('A.createElement(E3,{nativeOnMobile:!0,value:C,options:Object.keys(Jrc[e]),displayResolver:O=>O,',
         'A.createElement(E3,{nativeOnMobile:!0,value:C,options:Object.keys(Jrc[e]),displayResolver:O=>O==="Default Light"?"默认浅色":O==="Default Dark"?"默认深色":O,'),
        ('A.createElement(Irc,{label:"Background",value:t,',
         'A.createElement(Irc,{label:"背景颜色 (Background)",value:t,'),
        ('A.createElement(Irc,{label:"Foreground",value:v,',
         'A.createElement(Irc,{label:"文字前景色 (Foreground)",value:v,'),
        ('A.createElement(Irc,{label:"Accent",value:x,',
         'A.createElement(Irc,{label:"强调主题色 (Accent)",value:x,'),

        ('displayName:"Full machine",shortDisplayName:"Machine",shortDescription:"All terminal commands require review. The agent can read or write to any file in the machine."',
         'displayName:"完全本机模式 (Full Machine)",shortDisplayName:"完全本机",shortDescription:"所有终端命令均需人工审批。智能体可读取或写入本机上的任意文件。"'),
        ('A.createElement("span",null,"Learn more about"," ",A.createElement("span",{className:"font-semibold"},Ya))',
         'A.createElement("span",null,"了解更多关于"," ",A.createElement("span",{className:"font-semibold"},Ya))'),
        ('pMb=()=>A.createElement(mMb,{description:"Whether the agent asks you to review its documents.",setting:"artifactReview",testId:"artifact-review-overrides-trigger"})',
         'pMb=()=>A.createElement(mMb,{description:"智能体在生成或修改工件规划时是否请求您确认。",setting:"artifactReview",testId:"artifact-review-overrides-trigger"})'),
        ('A.createElement("span",null,"Type"," ",A.createElement("code",{className:"px-1.5 py-0.5 rounded bg-secondary text-foreground font-mono text-[11px] border border-border"},"/")," ","and select"," ",A.createElement("code",{className:"px-1.5 py-0.5 rounded bg-secondary text-foreground font-mono text-[11px] border border-border"},"plan")," ","to have the agent generate a plan.")',
         'A.createElement("span",null,"输入"," ",A.createElement("code",{className:"px-1.5 py-0.5 rounded bg-secondary text-foreground font-mono text-[11px] border border-border"},"/")," ","并选择"," ",A.createElement("code",{className:"px-1.5 py-0.5 rounded bg-secondary text-foreground font-mono text-[11px] border border-border"},"plan")," ","可让智能体生成执行规划。")'),
        ('label:"Plan Review Policy"', 'label:"规划审查策略"'),
        ('label:"Commands Outside Sandbox"', 'label:"沙箱外执行命令"'),
        ('description:"Configure allowed commands outside the sandbox."', 'description:"配置可在沙箱隔离外直接运行的终端命令。"'),
        ('description:"Allow/deny agent command execution outside the sandbox."', 'description:"配置允许或禁止智能体在沙箱外直接执行的终端命令。"'),
        ('onClick:()=>{Aa("network")}},"Open"', 'onClick:()=>{Aa("network")}},"打开"'),
        ('onClick:()=>{Aa("file")}},"Open"', 'onClick:()=>{Aa("file")}},"打开"'),
        ('onClick:()=>{Aa("command")}},"Open"', 'onClick:()=>{Aa("command")}},"打开"'),
        ('onClick:()=>{Aa("unsandboxed")}},"Open"', 'onClick:()=>{Aa("unsandboxed")}},"打开"'),
        ('A.createElement(w3,{title:"Browser",subtitle:', 'A.createElement(w3,{title:"浏览器自动化",subtitle:'),
        ('null,"Configure the browser subagent. It requires"," ",A.createElement("a",{href:"https://www.google.com/chrome/",target:"_blank",rel:"noopener noreferrer",className:"text-link hover:underline"},"Google Chrome")," ","to be installed.",(K||J)&&A.createElement(A.Fragment,null," ","The browser subagent can be invoked by typing /browser in the conversation input box."))',
         'null,"配置浏览器自动化子智能体。此功能需要设备安装有"," ",A.createElement("a",{href:"https://www.google.com/chrome/",target:"_blank",rel:"noopener noreferrer",className:"text-link hover:underline"},"Google Chrome")," ","浏览器。",(K||J)&&A.createElement(A.Fragment,null," ","在对话输入框中输入 /browser 即可唤出该智能体。"))'),

        ('A.createElement("a",{href:F.docsCustomizations,target:"_blank",rel:"noopener noreferrer",className:"text-link hover:underline"},"Learn more")',
         'A.createElement("a",{href:F.docsCustomizations,target:"_blank",rel:"noopener noreferrer",className:"text-link hover:underline"},"了解详情")'),
        ('A.createElement("p",{className:"text-muted-foreground"},"The breakdown below shows token usage from customizations like rules, skills, and MCP. If a budget is exceeded, large rules are demoted to path pointers and large customizations are excluded automatically.")',
         'A.createElement("p",{className:"text-muted-foreground"},"下方展示了规则 (Rules)、技能 (Skills) 与 MCP 扩展等自定义项所消耗的 Token 统计。若超出预算上限，过大的规则将降级为文件路径指针，超出部分的自定义项将被自动忽略。")'),
        ('D?"Hide breakdown":`Show ${C.length} breakdown${C.length===1?"":"s"}`',
         'D?"收起用量明细":`查看 ${C.length} 项明细`'),
        ('A.createElement("span",{className:"font-medium text-secondary-foreground"},"Rules")',
         'A.createElement("span",{className:"font-medium text-secondary-foreground"},"规则规范 (Rules)")'),
        ('y.length>0&&A.createElement(w3,\n{title:"Skills",count:y.length,collapsible:!0}',
         'y.length>0&&A.createElement(w3,\n{title:"技能列表 (Skills)",count:y.length,collapsible:!0}'),
        ('B.length>0&&A.createElement(w3,{title:"Rules",count:B.length,collapsible:!0}',
         'B.length>0&&A.createElement(w3,{title:"规则规范 (Rules)",count:B.length,collapsible:!0}'),
        ('e.openConfigFile?"Use Add MCP to browse the store, or add a custom server via the MCP config.":"Use Add MCP to browse the store."',
         'e.openConfigFile?"点击“添加 MCP 服务”浏览插件扩展商店，或通过 MCP 配置文件添加自定义服务。":"点击“添加 MCP 服务”浏览插件扩展商店。"'),
        ('onClick:()=>{da("bwg_plugins")}},"Customize"', 'onClick:()=>{da("bwg_plugins")}},"自定义配置"'),
    ]

    for target, repl in phase3_replacements:
        content = content.replace(target, repl)

    # 标记已完成第三阶段汉化，避免重复修补
    content += "\n/* agI18nPhase3 */\n"
    print("[web-patch] Applied Phase 3 Chinese translations")

    # 11. Chinese Localization (Web UI Phase 4 - 工具执行、差异对比、MCP与技能、权限管理与全局状态)
    phase4_replacements = [
        # 11a. 工具执行与实时步骤状态
        ('case "terminal":return"Running command";case "edit":return`Editing ${Ayb([a],b)}`;default:return"Exploring"',
         'case "terminal":return"正在运行命令";case "edit":return`正在编辑 ${Ayb([a],b)}`;default:return"正在探索分析..."'),
        ('b.length>0&&(b=Ayb(b,c),e.push(b?`Explored ${b}`:"Explored"))',
         'b.length>0&&(b=Ayb(b,c),e.push(b?`已分析 ${b}`:"已完成探索分析"))'),
        ('a.length>0&&e.push(`${e.length===0?"Ran":"ran"} ${a.length===1?"command":"commands"}`)',
         'a.length>0&&e.push(`执行了 ${a.length} 个终端命令`)'),
        ('f.length>0&&\n(c=Ayb(f,c),e.push(`${e.length===0?"Edited":"edited"} ${c}`));return e.length>0?e.join(", "):"Done"',
         'f.length>0&&\n(c=Ayb(f,c),e.push(`编辑了 ${c}`));return e.length>0?e.join("，"):"已完成"'),
        ('return a?`Searching ${a}`:void 0', 'return a?`正在搜索 ${a}`:void 0'),
        ('if(b.step.case==="viewFile"||a.metadata?.toolCall?.name==="read_file"||wf(a)?.aggregationKey==="files")return c?`Reading ${c}`:void 0',
         'if(b.step.case==="viewFile"||a.metadata?.toolCall?.name==="read_file"||wf(a)?.aggregationKey==="files")return c?`正在读取 ${c}`:void 0'),
        ('(a=yf(b.step.value.directoryPathUri))?`Listing ${a}`:void 0',
         '(a=yf(b.step.value.directoryPathUri))?`正在列出目录 ${a}`:void 0'),
        ('if(tM(a))return c?`Editing ${c}`:void 0',
         'if(tM(a))return c?`正在编辑 ${c}`:void 0'),
        ('id:"execution",key:"phase-execution",label:"Tool Execution",shortLabel:"Execution"',
         'id:"execution",key:"phase-execution",label:"工具调用执行",shortLabel:"工具执行"'),
        ('"Run command step not found"', '"未找到命令执行步骤"'),
        ('{label:"Best-of-N Started"}', '{label:"多模型对比已开始"}'),
        ('{label:"Best-of-N Ended"}', '{label:"多模型对比已结束"}'),

        # 11b. 差异对比与评审布局 (Diff View)
        ('title:"Side-by-side layout"', 'title:"左右分栏对比 (Side-by-Side)"'),
        ('A.createElement("span",null,"Side-by-Side")', 'A.createElement("span",null,"左右分栏")'),
        ('title:"Stacked layout"', 'title:"上下并排对比 (Stacked)"'),
        ('A.createElement("span",\nnull,"Stacked")', 'A.createElement("span",\nnull,"上下并排")'),
        ('"Reject all"),A.createElement("button"', '"全部拒绝"),A.createElement("button"'),
        ('"Accept all"))};var NTb=', '"全部采纳"))};var NTb='),

        # 11c. 模型选择与配额提示
        ('primaryAction:{label:"Select Model",onClick:()=>{b(!0)}}',
         'primaryAction:{label:"选择模型",onClick:()=>{b(!0)}}'),
        ('A.createElement(ty,{id:f},"Add Model")', 'A.createElement(ty,{id:f},"添加模型")'),
        ('"aria-label":"Edit Model"', '"aria-label":"编辑模型"'),
        ('label:"No Model Selected"', 'label:"未选择模型"'),
        ('title:"Model Quota"', 'title:"模型配额"'),
        ('title:"Model Credits"', 'title:"模型积分与额度"'),
        ('title:"Model quota reached"', 'title:"已达到模型配额上限"'),

        # 11d. 自定义项、MCP扩展服务与技能规则
        ('title:"Subagents"', 'title:"子智能体列表"'),
        ('title:"Installed MCP Servers"', 'title:"已安装的 MCP 扩展服务"'),
        ('title:"Refresh MCP servers"', 'title:"刷新 MCP 服务列表"'),
        ('"aria-label":"Refresh MCP servers"', '"aria-label":"刷新 MCP 服务列表"'),
        (',"Add MCP",A.createElement(W,{name:"add"', ',"添加 MCP 服务",A.createElement(W,{name:"add"'),
        ('"Open MCP Config"', '"打开 MCP 配置文件"'),
        ('title:"MCP Configuration Error:"', 'title:"MCP 配置错误:"'),
        ('"Loading MCP servers..."', '"正在加载 MCP 服务..."'),
        ('"No MCP servers installed"', '"未安装任何 MCP 服务"'),
        ('"Loading workspace customizations..."', '"正在加载工作区自定义项与技能..."'),
        ('title:"Customize Global Skills",settings:[Wi.SKILLS]', 'title:"全局技能 (Skills) 自定义",settings:[Wi.SKILLS]'),
        ('title:"Custom Agents",settings:[Wi.CUSTOM_AGENTS]', 'title:"自定义智能体 (Custom Agents)",settings:[Wi.CUSTOM_AGENTS]'),
        ('title:"MCP Servers",settings:[Wi.MCP]', 'title:"MCP 扩展服务 (MCP Servers)",settings:[Wi.MCP]'),
        ('title:"Updater",settings:[Yi.AUTO_CHECK_FOR_UPDATES]', 'title:"应用更新",settings:[Yi.AUTO_CHECK_FOR_UPDATES]'),
        ('title:"Commands",count:g.length', 'title:"快捷指令 (Commands)",count:g.length'),
        ('title:"Skills",count:h.length', 'title:"技能 (Skills)",count:h.length'),
        ('title:"Agents",count:a.agents.length', 'title:"智能体 (Agents)",count:a.agents.length'),
        ('title:"MCP servers",\ncount:a.mcpServers.length', 'title:"MCP 服务",\ncount:a.mcpServers.length'),
        ('title:"Rules",count:a.rules.length', 'title:"规则规范 (Rules)",count:a.rules.length'),
        ('title:"UI extensions",count:b.length', 'title:"UI 界面扩展",count:b.length'),
        ('title:"Automations",\ncount:c.length', 'title:"自动化任务 (Automations)",\ncount:c.length'),
        ('automation:{title:"Automations",sidebarLabel:"Automations",searchPlaceholder:"Search automations...",emptyMessageSingular:"automation",emptyMessagePlural:"automations"',
         'automation:{title:"自动化任务",sidebarLabel:"自动化任务",searchPlaceholder:"搜索自动化任务...",emptyMessageSingular:"自动化任务",emptyMessagePlural:"自动化任务"'),

        # 11e. 权限管理与控制
        ('title:"File Permissions"', 'title:"文件访问权限"'),
        ('title:"Permission Settings"', 'title:"权限管理"'),
        ('label:"Tool Permissions"', 'label:"工具执行权限"'),
        ('title:"Terminal & Tooling Permissions"', 'title:"终端与工具权限"'),
        ('title:"Browser Actuation Permissions"', 'title:"浏览器操作权限"'),
        ('label:"Permission Preset"', 'label:"预设权限方案"'),
        ('title:"Network Permissions"', 'title:"网络访问权限"'),
        ('title:"Permission Details"', 'title:"权限详细信息"'),
        ('title:"Local Permissions"', 'title:"本地权限"'),
        ('title:"Global Permissions"', 'title:"全局权限"'),
        ('"Terminal Commands"', '"终端命令"'),
        ('"Terminal commands the agent can execute in this workspace."', '"智能体在此工作区中可执行的终端命令。"'),
        ('"Terminal input"', '"终端输入"'),
        ('size:"xs",onClick:e,className:aj("rounded-sm !font-normal","!pl-0")},"Configure")',
         'size:"xs",onClick:e,className:aj("rounded-sm !font-normal","!pl-0")},"配置权限")'),

        # 11f. 通用操作与空状态
        ('emptyMessage:a="No results found"', 'emptyMessage:a="未找到匹配结果"'),
        ('emptyMessage:c="No matching items"', 'emptyMessage:c="暂无匹配项"'),
        ('b?"Get started":"Next"', 'b?"开始使用":"下一步"'),
        ('"aria-label":"Good response"', '"aria-label":"好评 (回答满意)"'),
        ('"aria-label":"Bad response"', '"aria-label":"差评 (回答不佳)"'),
        ('label:g="Scroll to Bottom"', 'label:g="滚动到底部"'),
        ('className:"flex-grow min-w-0 truncate"},"New Terminal")', 'className:"flex-grow min-w-0 truncate"},"新建终端")'),
    ]

    for target, repl in phase4_replacements:
        content = content.replace(target, repl)

    # 标记已完成全部阶段汉化
    content += "\n/* agI18nPhaseFinal */\n"
    print("[web-patch] Applied Phase 4 (Final) Chinese translations")

    # 12. Chinese Localization (Web UI Polish - 全盘润色与边缘词条补漏)
    polish_replacements = [
        # 12a. 输入框占位符补全
        ('placeholder:"Search steps..."', 'placeholder:"搜索执行步骤..."'),
        ('placeholder:"Search MCP servers by name"', 'placeholder:"按名称搜索 MCP 服务..."'),
        ('placeholder:"Enter file or directory path..."', 'placeholder:"输入文件或目录路径..."'),
        ('placeholder:"Conversation name"', 'placeholder:"会话名称"'),
        ('placeholder:"Enter authorization code..."', 'placeholder:"输入授权验证码..."'),
        ('placeholder:"Select or enter a workspace URI"', 'placeholder:"选择或输入工作区路径..."'),
        ('placeholder:"Paste code here"', 'placeholder:"在此粘贴代码..."'),
        ('placeholder:"Search GoB repositories..."', 'placeholder:"搜索代码仓库..."'),

        # 12b. 常用浮层与操作按钮提示
        ('tooltip:"Cancel Sending Message"', 'tooltip:"取消发送消息"'),
        ('tooltip:"Cancel Task"', 'tooltip:"取消任务"'),
        ('tooltip:"Cancel All Tasks"', 'tooltip:"取消全部任务"'),
        ('tooltip:"Add MCP Server"', 'tooltip:"添加 MCP 服务"'),
        ('tooltip:"Open in new window"', 'tooltip:"在新窗口中打开"'),
        ('tooltip:"More actions"', 'tooltip:"更多操作"'),
        ('title:"Close (Esc)"', 'title:"关闭 (Esc)"'),
        ('title:"Clear search (Esc)"', 'title:"清空搜索 (Esc)"'),
        ('title:"Next match (Enter)"', 'title:"下一个匹配项 (Enter)"'),
        ('title:"Previous match (Shift+Enter)"', 'title:"上一个匹配项 (Shift+Enter)"'),
        ('title:"Zoom in (+)"', 'title:"放大 (+)"'),
        ('title:"Zoom out (-)"', 'title:"缩小 (-)"'),
        ('title:"Reset zoom (0)"', 'title:"重置缩放 (0)"'),
        ('title:"Copy path"', 'title:"复制路径"'),
        ('title:"Copy output"', 'title:"复制输出结果"'),
        ('title:"Copy thinking"', 'title:"复制思考过程"'),
        ('title:"Copy command"', 'title:"复制命令"'),
        ('title:"Copy error to clipboard"', 'title:"复制错误信息到剪贴板"'),
        ('title:"Click to copy URL"', 'title:"点击复制网址"'),
        ('title:"Click to copy full command"', 'title:"点击复制完整命令"'),
        ('title:"Open in external browser"', 'title:"使用外部浏览器打开"'),
        ('title:"Open side-by-side view"', 'title:"打开左右分栏视图"'),
        ('title:"Capture screenshot"', 'title:"截取屏幕截图"'),
        ('title:"Capture console logs"', 'title:"捕获控制台日志"'),
        ('title:"Download PDF"', 'title:"下载 PDF"'),
        ('title:"Download SVG"', 'title:"下载 SVG 图片"'),
        ('title:"Double-click to reset panel sizes"', 'title:"双击重置面板大小"'),
        ('title:"Share Conversation (Preview)"', 'title:"分享对话 (预览版)"'),
        ('title:"Telemetry is disabled in Settings"', 'title:"遥测上报已在系统设置中关闭"'),
        ('title:"Open in new tab"', 'title:"在新标签页中打开"'),

        # 12c. 弹窗标题与设置分栏
        ('title:"Artifacts"', 'title:"工件文档 (Artifacts)"'),
        ('title:"Background Tasks"', 'title:"后台任务"'),
        ('title:"Pinned Conversations"', 'title:"置顶对话"'),
        ('title:"Danger Zone"', 'title:"危险操作区"'),
        ('title:"Files Changed"', 'title:"已修改文件"'),
        ('title:"Rename Conversation"', 'title:"重命名对话"'),
        ('title:"Rename Group"', 'title:"重命名分组"'),
        ('title:"New Group"', 'title:"新建分组"'),
        ('title:"Delete Task"', 'title:"删除任务"'),
        ('title:"Delete Skill"', 'title:"删除技能"'),
        ('title:"Delete MCP Server"', 'title:"删除 MCP 服务"'),
        ('title:"Manage Skills"', 'title:"管理技能"'),
        ('title:"Skills & Rules"', 'title:"技能与规则"'),
        ('title:"Installed Skills"', 'title:"已安装技能"'),
        ('title:"Update Available"', 'title:"发现新版本"'),
        ('title:"Error Loading Models"', 'title:"加载模型失败"'),
        ('title:"No Models Available"', 'title:"暂无可用模型"'),
        ('title:"Conversation Archived"', 'title:"对话已归档"'),
        ('title:"Could not create project"', 'title:"创建项目失败"'),
        ('title:"Failed to stop agent"', 'title:"停止智能体失败"'),
        ('title:"Failed to create terminal"', 'title:"创建终端失败"'),
        ('title:"Terminals"', 'title:"终端列表"'),
        ('title:"Steps"', 'title:"执行步骤"'),
        ('title:"Plan"', 'title:"执行规划"'),
        ('title:"Setup required"', 'title:"需要配置"'),
        ('title:"Verification required"', 'title:"需要验证"'),
        ('title:"Action required"', 'title:"需要确认操作"'),
        ('title:"System Instruction"', 'title:"系统提示词"'),
        ('title:"Agent Behavior"', 'title:"智能体行为"'),
        ('title:"Notification Preferences"', 'title:"通知偏好设置"'),
        ('title:"Chat Settings"', 'title:"对话设置"'),
        ('title:"Workspace File Access"', 'title:"工作区文件访问"'),
        ('title:"Workspace Command Access"', 'title:"工作区命令访问"'),
        ('title:"Workspace Web Access"', 'title:"工作区网络访问"'),
        ('title:"Close Settings"', 'title:"关闭设置"'),
        ('title:"Confirm Undo"', 'title:"确认撤销"'),

        # 12d. 交互占位提示符 (Placeholders)
        ('placeholder:"Search..."', 'placeholder:"搜索..."'),
        ('placeholder:"Search across files..."', 'placeholder:"在全局文件中搜索..."'),
        ('placeholder:"Search skills\\u2026"', 'placeholder:"搜索技能…"'),
        ('placeholder:"Search all skills on Agent Market\\u2026"', 'placeholder:"在智能体市场中搜索所有技能…"'),
        ('placeholder:"Search customizations..."', 'placeholder:"搜索自定义配置..."'),
        ('placeholder:"Search tabs, files, plugins, subagents, artifacts, tasks..."', 'placeholder:"搜索标签页、文件、插件、子智能体、产物与任务..."'),
        ('placeholder:"Search by name or Cascade ID..."', 'placeholder:"按名称或 Cascade ID 搜索..."'),
        ('placeholder:"Filter resources..."', 'placeholder:"过滤资源..."'),
        ('placeholder:"Find"', 'placeholder:"查找"'),
        ('placeholder:"Enter a prompt for the agent to run..."', 'placeholder:"输入让智能体运行的提示词..."'),
        ('placeholder:"Enter URL pattern..."', 'placeholder:"输入 URL 匹配规则..."'),
        ('placeholder:"Enter a URL (e.g. http://localhost:8080)"', 'placeholder:"输入 URL (例如 http://localhost:8080)"'),
        ('placeholder:"Enter command (e.g., git, blaze)..."', 'placeholder:"输入命令 (例如 git, pnpm)..."'),
        ('placeholder:"Enter device name..."', 'placeholder:"输入设备名称..."'),
        ('placeholder:"Enter directory path..."', 'placeholder:"输入目录路径..."'),
        ('placeholder:"Enter project name..."', 'placeholder:"输入项目名称..."'),
        ('placeholder:"Enter tool name or server..."', 'placeholder:"输入工具名称或服务..."'),
        ('placeholder:"Enter workspace name (e.g., my-feature)"', 'placeholder:"输入工作区名称 (例如 my-feature)"'),
        ('placeholder:"Enter workspace name (e.g., my-cog-feature)"', 'placeholder:"输入工作区名称 (例如 my-cog-feature)"'),
        ('placeholder:"Type absolute path or navigate folders..."', 'placeholder:"输入绝对路径或浏览文件夹..."'),
        ('placeholder:"Select branch"', 'placeholder:"选择分支"'),
        ('placeholder:"Paste code"', 'placeholder:"粘贴代码"'),
        ('placeholder:"Paste auth code"', 'placeholder:"粘贴认证代码"'),
        ('placeholder:"Write a comment..."', 'placeholder:"撰写评论..."'),
        ('placeholder:"Please list the steps to reproduce the issue"', 'placeholder:"请列出复现此问题的具体步骤"'),
        ('placeholder:"Prompt to execute on schedule..."', 'placeholder:"定时执行的提示词..."'),
        ('placeholder:"Prompt to run when triggered..."', 'placeholder:"触发时执行的提示词..."'),
        ('placeholder:"Variant Name"', 'placeholder:"变体名称"'),
        ('placeholder:"Group name"', 'placeholder:"分组名称"'),
        ('placeholder:"New hook name"', 'placeholder:"新 Hook 名称"'),
        ('placeholder:"Other (write your answer)"', 'placeholder:"其他 (填写您的回答)"'),
        ('(Optional) Tell us more or type your reason...', '(可选) 描述更多详情或输入原因...'),
        ('placeholder:"Add recent remote workspace"', 'placeholder:"添加最近远程工作区"'),
        ('placeholder:"Cron expression e.g. 0 */6 * * *"', 'placeholder:"Cron 表达式 例如 0 */6 * * *"'),
        ('placeholder:"Absolute path to the Chrome/Chromium executable"', 'placeholder:"Chrome/Chromium 可执行文件绝对路径"'),

        # 12e. 悬浮提示说明 (Tooltips)
        ('tooltip:"Settings"', 'tooltip:"设置"'),
        ('tooltip:"Delete"', 'tooltip:"删除"'),
        ('tooltip:"Delete comment"', 'tooltip:"删除评论"'),
        ('tooltip:"Delete workspace"', 'tooltip:"删除工作区"'),
        ('tooltip:"Edit comment"', 'tooltip:"编辑评论"'),
        ('tooltip:"Back"', 'tooltip:"返回"'),
        ('tooltip:"Clear"', 'tooltip:"清除"'),
        ('tooltip:"Copy Content"', 'tooltip:"复制内容"'),
        ('tooltip:"Copy Path"', 'tooltip:"复制路径"'),
        ('tooltip:"Rename"', 'tooltip:"重命名"'),
        ('tooltip:"Refresh"', 'tooltip:"刷新"'),
        ('tooltip:"Search"', 'tooltip:"搜索"'),
        ('tooltip:"Minimize"', 'tooltip:"最小化"'),
        ('tooltip:"More Actions"', 'tooltip:"更多操作"'),
        ('tooltip:"Export as PDF"', 'tooltip:"导出为 PDF"'),
        ('tooltip:"Open folder"', 'tooltip:"打开文件夹"'),
        ('tooltip:"Open in preview"', 'tooltip:"在预览中打开"'),
        ('tooltip:"Open in Code Search"', 'tooltip:"在代码搜索中打开"'),
        ('tooltip:"Open in Notebook View"', 'tooltip:"在 Notebook 视图中打开"'),
        ('tooltip:"Previous question"', 'tooltip:"上一题"'),
        ('tooltip:"Next question"', 'tooltip:"下一题"'),
        ('tooltip:"Table options"', 'tooltip:"表格选项"'),
        ('tooltip:"Command Center"', 'tooltip:"命令中心"'),
        ('tooltip:"Ask the agent to diagnose and fix this server"', 'tooltip:"请求智能体诊断并修复此服务"'),
        ('tooltip:"Create a Plugin with the Agent"', 'tooltip:"使用智能体创建插件"'),
        ('tooltip:"Remount workspace"', 'tooltip:"重新挂载工作区"'),
        ('tooltip:"Unmount workspace"', 'tooltip:"卸载工作区"'),
        ('tooltip:"Trajectory Debug View"', 'tooltip:"轨迹调试视图"'),

        # 12f. 无障碍与操作标签 (Aria Labels)
        ('"aria-label":"Send message"', '"aria-label":"发送消息"'),
        ('"aria-label":"Stop execution"', '"aria-label":"停止执行"'),
        ('"aria-label":"Close"', '"aria-label":"关闭"'),
        ('"aria-label":"Cancel"', '"aria-label":"取消"'),
        ('"aria-label":"File Explorer"', '"aria-label":"文件资源管理器"'),
        ('"aria-label":"New Conversation"', '"aria-label":"新建对话"'),
        ('"aria-label":"Fork Conversation"', '"aria-label":"分叉对话"'),
        ('"aria-label":"Archive conversation"', '"aria-label":"归档对话"'),
        ('"aria-label":"Delete Terminal"', '"aria-label":"删除终端"'),
        ('"aria-label":"Split Terminal"', '"aria-label":"拆分终端"'),
        ('"aria-label":"Open Terminal"', '"aria-label":"打开终端"'),
        ('"aria-label":"Search Conversations"', '"aria-label":"搜索对话历史"'),
        ('"aria-label":"Toggle Sidebar"', '"aria-label":"切换侧边栏"'),
        ('"aria-label":"Toggle sidebar"', '"aria-label":"切换侧边栏"'),
        ('"aria-label":"Close Sidebar"', '"aria-label":"关闭侧边栏"'),
        ('"aria-label":"Clear search"', '"aria-label":"清空搜索"'),
        ('"aria-label":"Clear Search"', '"aria-label":"清空搜索"'),
        ('"aria-label":"Copy command"', '"aria-label":"复制命令"'),
        ('"aria-label":"Copy path"', '"aria-label":"复制路径"'),
        ('"aria-label":"Copy value"', '"aria-label":"复制内容"'),
        ('"aria-label":"Next match"', '"aria-label":"下一个匹配项"'),
        ('"aria-label":"Previous match"', '"aria-label":"上一个匹配项"'),
        ('"aria-label":"Match case"', '"aria-label":"区分大小写"'),
        ('"aria-label":"Match whole word"', '"aria-label":"全字匹配"'),
        ('"aria-label":"Use regular expression"', '"aria-label":"使用正则表达式"'),
        ('"aria-label":"Dismiss toast"', '"aria-label":"关闭通知"'),
        ('"aria-label":"Dismiss notification"', '"aria-label":"关闭通知"'),
        ('"aria-label":"Dismiss error"', '"aria-label":"忽略错误"'),
        ('"aria-label":"Dismiss Tip"', '"aria-label":"关闭提示"'),
        ('"aria-label":"Zoom in"', '"aria-label":"放大"'),
        ('"aria-label":"Zoom out"', '"aria-label":"缩小"'),
        ('"aria-label":"Zoom In"', '"aria-label":"放大"'),
        ('"aria-label":"Zoom Out"', '"aria-label":"缩小"'),
        ('"aria-label":"Reset zoom"', '"aria-label":"重置缩放"'),
        ('"aria-label":"Toggle file diff"', '"aria-label":"切换文件差异对比"'),
        ('"aria-label":"Stop subagent"', '"aria-label":"停止子智能体"'),
        ('"aria-label":"Cancel step"', '"aria-label":"取消步骤"'),
        ('"aria-label":"Cancel Task"', '"aria-label":"取消任务"'),
        ('"aria-label":"Cancel Sending Message"', '"aria-label":"取消发送消息"'),
        ('"aria-label":"Close Logs Modal"', '"aria-label":"关闭日志弹窗"'),
        ('"aria-label":"Close panel"', '"aria-label":"关闭面板"'),
        ('"aria-label":"Close skills panel"', '"aria-label":"关闭技能面板"'),
        ('"aria-label":"Message input"', '"aria-label":"消息输入框"'),
        ('"aria-label":"Conversation name"', '"aria-label":"对话名称"'),
        ('"aria-label":"Add MCP Server"', '"aria-label":"添加 MCP 服务"'),
        ('"aria-label":"Refresh skills"', '"aria-label":"刷新技能"'),
        ('"aria-label":"Refresh customizations"', '"aria-label":"刷新自定义配置"'),
        ('"aria-label":"Download PDF"', '"aria-label":"下载 PDF"'),
        ('"aria-label":"Download SVG"', '"aria-label":"下载 SVG"'),
        ('"aria-label":"New tab"', '"aria-label":"新建标签页"'),
        ('"aria-label":"Next Page"', '"aria-label":"下一页"'),
        ('"aria-label":"Previous Page"', '"aria-label":"上一页"'),
        ('"aria-label":"Next question"', '"aria-label":"下一题"'),
        ('"aria-label":"Previous question"', '"aria-label":"上一题"'),
        ('"aria-label":"Select Agent"', '"aria-label":"选择智能体"'),
        ('"aria-label":"Select Environment"', '"aria-label":"选择环境"'),
        ('"aria-label":"Show Remote Control QR code"', '"aria-label":"显示远程控制二维码"'),
        ('"aria-label":"View comments"', '"aria-label":"查看批注评论"'),
        ('"aria-label":"Open in new tab"', '"aria-label":"在新标签页中打开"'),
        ('"aria-label":"Open in external browser"', '"aria-label":"在外部浏览器中打开"'),
        ('"aria-label":"Reload app"', '"aria-label":"重新加载应用"'),
        ('"aria-label":"Settings"', '"aria-label":"设置"'),
        ('"aria-label":"Open settings menu"', '"aria-label":"打开设置菜单"'),
        ('"aria-label":"Search"', '"aria-label":"搜索"'),
        ('"aria-label":"Go Back"', '"aria-label":"返回"'),
        ('"aria-label":"Go Forward"', '"aria-label":"前进"'),
        ('"aria-label":"Back"', '"aria-label":"返回"'),
        ('"aria-label":"Forward"', '"aria-label":"前进"'),

        # 12g. 常用对话框与通用提示 (Common Dialogs & Alerts)
        ('"No conversations found"', '"未找到任何对话历史"'),
        ('"No results found"', '"未找到匹配结果"'),
        ('"Are you sure you want to delete "', '"您确定要删除 "'),
        ('"Select Model"', '"选择模型"'),
        ('"Select Theme"', '"选择主题"'),
        ('"Are you sure you want to delete this handler?"', '"您确定要删除此处理器吗？"'),
        ('"Are you sure you want to delete this hook card?"', '"您确定要删除此 Hook 卡片吗？"'),
        ('"Are you sure you want to delete the workspace"', '"您确定要删除该工作区"'),
        ('"Delete Conversation"', '"删除对话"'),
        ('"Delete Task"', '"删除任务"'),
        ('"Cancel Task"', '"取消任务"'),
        ('placeholder:"Target text in PDF..."', 'placeholder:"在 PDF 中定位目标文本..."'),
        ('tooltip:"Remote Control"', 'tooltip:"远程协同控制"'),
    ]

    for target, repl in polish_replacements:
        content = content.replace(target, repl)

    # 标记已完成全部阶段汉化与全盘润色
    content += "\n/* agI18nComplete */\n"
    print("[web-patch] Applied Complete Polish Chinese translations")




    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("[web-patch] All patches applied successfully to main.js")
    return True

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "main.js")
    if not patch_main(path):
        sys.exit(1)
