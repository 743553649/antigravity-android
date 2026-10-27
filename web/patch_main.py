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

    # If already patched with v2 modal, shared storage, and resume sync, skip
    if "agTestConn" in content and "agLocalModels" in content and "agSd" in content and "agTrajectoriesRegistry" in content:
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

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("[web-patch] All patches applied successfully to main.js")
    return True

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "main.js")
    if not patch_main(path):
        sys.exit(1)
