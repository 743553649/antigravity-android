package com.agy.bridge;

import android.content.Context;

import com.agy.oauth.OAuthManager;
import com.agy.ui.MainActivity;

/** Opens a URL in the system browser (auth URLs included). */
public final class ExternalUrlBridge {

    private final Context appContext;
    private final OAuthManager oauth;

    public ExternalUrlBridge(Context appContext, OAuthManager oauth) {
        this.appContext = appContext;
        this.oauth = oauth;
    }

    public void open(String url) {
        if (url == null) {
            return;
        }
        Context target = (MainActivity.activeActivity != null)
                ? MainActivity.activeActivity
                : appContext;
        oauth.openInBrowser(target, url);
    }
}
