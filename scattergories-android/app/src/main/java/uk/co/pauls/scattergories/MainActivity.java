package uk.co.pauls.scattergories;

import android.app.Activity;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.os.Handler;
import android.os.Looper;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.Locale;
import java.util.Random;

public class MainActivity extends Activity {
    private final String letters = "ABCDEFGHJKLMNPRSTW";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Random random = new Random();
    private TextView letterView, timerView, statusView;
    private Button rollButton, resetButton;
    private CountDownTimer countdown;
    private Runnable spinner;
    private long spinEnd;
    private boolean spinning = false;
    private ToneGenerator tone;
    private final int bg = Color.rgb(14,23,42), panel = Color.rgb(25,38,62);
    private final int accent = Color.rgb(91,190,255), white = Color.WHITE;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(bg);
        getWindow().setNavigationBarColor(bg);
        tone = new ToneGenerator(AudioManager.STREAM_ALARM, 85);
        buildUi();
    }
    private int dp(int v) { return (int)(v * getResources().getDisplayMetrics().density + .5f); }
    private GradientDrawable rounded(int color, int radius) {
        GradientDrawable d = new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius)); return d;
    }
    private TextView text(String s, int size, int color, boolean bold) {
        TextView t = new TextView(this); t.setText(s); t.setTextSize(size); t.setTextColor(color);
        t.setGravity(Gravity.CENTER); if (bold) t.setTypeface(Typeface.DEFAULT, Typeface.BOLD); return t;
    }
    private Button button(String s, int color) {
        Button b = new Button(this); b.setText(s); b.setTextSize(18); b.setAllCaps(false);
        b.setTextColor(white); b.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        b.setBackground(rounded(color, 28)); b.setPadding(dp(18),dp(10),dp(18),dp(10)); return b;
    }
    private void buildUi() {
        LinearLayout root = new LinearLayout(this); root.setOrientation(1); root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(dp(24),dp(24),dp(24),dp(22)); root.setBackgroundColor(bg);
        root.addView(text("Paul's Scattergories",29,white,true), new LinearLayout.LayoutParams(-1,dp(72)));
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(-1,dp(38)); sp.bottomMargin=dp(16);
        root.addView(text("ROLL A LETTER. BEAT THE CLOCK.",12,accent,true),sp);
        LinearLayout card = new LinearLayout(this); card.setOrientation(1); card.setGravity(Gravity.CENTER);
        card.setPadding(dp(16),dp(20),dp(16),dp(20)); card.setBackground(rounded(panel,30));
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(-1,0,1); cp.bottomMargin=dp(18); root.addView(card,cp);
        card.addView(text("YOUR LETTER",14,accent,true),new LinearLayout.LayoutParams(-1,dp(38)));
        letterView=text("?",104,white,true); letterView.setBackground(rounded(Color.rgb(35,54,84),26));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(180)); lp.setMargins(dp(8),dp(6),dp(8),dp(22)); card.addView(letterView,lp);
        timerView=text("3:00",58,white,true); card.addView(timerView,new LinearLayout.LayoutParams(-1,dp(90)));
        statusView=text("Ready when you are",16,Color.LTGRAY,false);
        LinearLayout.LayoutParams stp=new LinearLayout.LayoutParams(-1,dp(48)); stp.bottomMargin=dp(12); card.addView(statusView,stp);
        rollButton=button("🎲  Roll Dice",Color.rgb(0,125,210)); root.addView(rollButton,new LinearLayout.LayoutParams(-1,dp(64)));
        resetButton=button("Reset",Color.rgb(51,65,88)); LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(-1,dp(54)); rp.topMargin=dp(12); root.addView(resetButton,rp);
        setContentView(root);
        rollButton.setOnClickListener(v -> roll()); resetButton.setOnClickListener(v -> reset());
    }
    private void roll() {
        if (spinning) return;
        stopCountdown(); spinning=true; rollButton.setEnabled(false); rollButton.setAlpha(.6f);
        statusView.setText("Rolling..."); spinEnd=System.currentTimeMillis()+3000;
        spinner=new Runnable() { public void run() {
            if (!spinning) return;
            letterView.setText(String.valueOf(letters.charAt(random.nextInt(letters.length()))));
            if (System.currentTimeMillis()<spinEnd) handler.postDelayed(this,65);
            else {
                spinning=false; letterView.setText(String.valueOf(letters.charAt(random.nextInt(letters.length()))));
                rollButton.setEnabled(true); rollButton.setAlpha(1f); statusView.setText("Go! You have 3 minutes"); startCountdown();
            }
        }};
        handler.post(spinner);
    }
    private void startCountdown() {
        countdown=new CountDownTimer(180000,100) {
            public void onTick(long ms) { long s=(ms+999)/1000; timerView.setText(String.format(Locale.UK,"%d:%02d",s/60,s%60)); }
            public void onFinish() { timerView.setText("0:00"); statusView.setText("Time's up!"); alarm(); }
        }.start();
    }
    private void alarm() {
        try {
            tone.startTone(ToneGenerator.TONE_CDMA_ALERT_CALL_GUARD,500);
            handler.postDelayed(() -> tone.startTone(ToneGenerator.TONE_PROP_BEEP,350),600);
            handler.postDelayed(() -> tone.startTone(ToneGenerator.TONE_PROP_BEEP2,500),1050);
        } catch (Exception ignored) {}
    }
    private void stopCountdown() { if (countdown!=null) { countdown.cancel(); countdown=null; } }
    private void reset() {
        spinning=false; if (spinner!=null) handler.removeCallbacks(spinner); stopCountdown();
        letterView.setText("?"); timerView.setText("3:00"); statusView.setText("Ready when you are");
        rollButton.setEnabled(true); rollButton.setAlpha(1f);
    }
    @Override protected void onDestroy() {
        reset(); handler.removeCallbacksAndMessages(null); if (tone!=null) tone.release(); super.onDestroy();
    }
}
