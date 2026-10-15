package com.agy.ui.splash;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.util.AttributeSet;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;

/**
 * Lightweight native Android View animating three bouncing dots.
 * Replaces heavy Chromium WebView instance saving ~40 MB RAM.
 * Matches authentic Antigravity dot bounce: 3 dots, vertical bounce, 1.6s duration.
 */
public class NativeSplashDotsView extends View {

    private static final int DOT_COUNT = 3;
    private static final long DURATION_MS = 1600;

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float[] dotOffsets = new float[DOT_COUNT];
    private ValueAnimator animator;

    private float dotRadiusPx;
    private float dotGapPx;
    private float bounceDistancePx;

    public NativeSplashDotsView(Context context) {
        super(context);
        init();
    }

    public NativeSplashDotsView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    public NativeSplashDotsView(Context context, AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
        init();
    }

    private void init() {
        float density = getResources().getDisplayMetrics().density;
        // Standard dot dimensions: diameter ~4dp (radius 2dp), gap ~3dp, bounce distance ~4dp
        dotRadiusPx = 2.0f * density;
        dotGapPx = 3.0f * density;
        bounceDistancePx = 4.0f * density;

        paint.setStyle(Paint.Style.FILL);
        paint.setColor(Color.WHITE);
        paint.setAlpha(128); // ~0.5 opacity as in web version
    }

    public void setDotColor(int color) {
        paint.setColor(color);
        paint.setAlpha(128);
        invalidate();
    }

    public void startAnimation() {
        if (animator != null && animator.isRunning()) {
            return;
        }
        animator = ValueAnimator.ofFloat(0f, 1f);
        animator.setDuration(DURATION_MS);
        animator.setRepeatCount(ValueAnimator.INFINITE);
        animator.setInterpolator(new AccelerateDecelerateInterpolator());
        animator.addUpdateListener(new ValueAnimator.AnimatorUpdateListener() {
            @Override
            public void onAnimationUpdate(ValueAnimator animation) {
                float fraction = animation.getAnimatedFraction();
                for (int i = 0; i < DOT_COUNT; i++) {
                    // Delays: 0ms, 120ms, 240ms relative to 1600ms total
                    float delayFraction = (i * 120f) / DURATION_MS;
                    float dotProgress = (fraction - delayFraction + 1f) % 1f;
                    // Bounce happens in the first 30% of cycle (peak at 15%)
                    if (dotProgress <= 0.30f) {
                        float sub = dotProgress / 0.30f; // 0 to 1
                        // Peak bounce at sub = 0.5
                        float factor = (float) Math.sin(sub * Math.PI);
                        dotOffsets[i] = -bounceDistancePx * factor;
                    } else {
                        dotOffsets[i] = 0f;
                    }
                }
                invalidate();
            }
        });
        animator.start();
    }

    public void stopAnimation() {
        if (animator != null) {
            animator.cancel();
            animator = null;
        }
    }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (getVisibility() == VISIBLE) {
            startAnimation();
        }
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        stopAnimation();
    }

    @Override
    protected void onVisibilityChanged(View changedView, int visibility) {
        super.onVisibilityChanged(changedView, visibility);
        if (visibility == VISIBLE) {
            startAnimation();
        } else {
            stopAnimation();
        }
    }

    @Override
    protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
        float totalWidth = (DOT_COUNT * dotRadiusPx * 2) + ((DOT_COUNT - 1) * dotGapPx) + getPaddingLeft() + getPaddingRight();
        float totalHeight = (dotRadiusPx * 2) + (bounceDistancePx * 2) + getPaddingTop() + getPaddingBottom();
        setMeasuredDimension(
                resolveSize((int) Math.ceil(totalWidth), widthMeasureSpec),
                resolveSize((int) Math.ceil(totalHeight), heightMeasureSpec)
        );
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float totalDotsWidth = (DOT_COUNT * dotRadiusPx * 2) + ((DOT_COUNT - 1) * dotGapPx);
        float startX = (getWidth() - totalDotsWidth) / 2f + dotRadiusPx;
        float centerY = getHeight() / 2f;

        for (int i = 0; i < DOT_COUNT; i++) {
            float cx = startX + i * (dotRadiusPx * 2 + dotGapPx);
            float cy = centerY + dotOffsets[i];
            canvas.drawCircle(cx, cy, dotRadiusPx, paint);
        }
    }
}
