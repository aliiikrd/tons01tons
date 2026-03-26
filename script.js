/**
 * =============================================================================
 *   Telegram Mini App Script  -  @AllSocialSaversbot
 *   Developed by @whykurds
 * =============================================================================
 *
 *   This script ties together:
 *   1. The Telegram WebApp SDK  (Telegram.WebApp)
 *   2. The Monetag Rewarded Interstitial SDK  (show_XXXXX)
 *
 *   OVERVIEW:
 *   ---------
 *   When the user opens this Mini App from the bot's inline button, this
 *   script initializes the Telegram WebApp context, optionally preloads
 *   a Monetag ad, and then waits for the user to tap the "Watch Ad" button.
 *
 *   On button tap:
 *     1. Disable the button and show the loading overlay.
 *     2. Call the Monetag SDK function to show a Rewarded Interstitial.
 *     3. If the ad completes successfully:
 *        a. Show the success overlay with animated checkmark.
 *        b. Wait ~1.5 seconds for the animation to play.
 *        c. Send "ad_completed" to the bot via Telegram.WebApp.sendData().
 *        d. Close the Mini App via Telegram.WebApp.close().
 *     4. If the ad fails or is unavailable:
 *        a. Hide the loading overlay.
 *        b. Show an inline error message.
 *        c. Re-enable the button so the user can retry.
 *
 *   MONETAG SDK INTEGRATION NOTES:
 *   ------------------------------
 *   - The SDK is loaded in index.html via a <script> tag with data-zone and
 *     data-sdk attributes.  After loading, it creates a global function on
 *     the window object (e.g., window.show_XXXXX).
 *   - The function returns a Promise:
 *       .then()  -> ad was fully watched (reward the user)
 *       .catch() -> ad failed, was skipped, or no fill available
 *   - We use the "end" type (default) which resolves AFTER the ad is closed.
 *   - Preloading with { type: 'preload' } is attempted on page load to
 *     reduce delay when the user taps the button.
 *   - The ymid parameter is set to the Telegram user ID for postback tracking.
 *
 *   TELEGRAM WEBAPP SDK NOTES:
 *   --------------------------
 *   - Telegram.WebApp.ready() MUST be called to signal that the app is loaded.
 *   - Telegram.WebApp.sendData(string) sends a UTF-8 string (max 4096 bytes)
 *     back to the bot.  The bot receives it as a web_app_data message.
 *   - Telegram.WebApp.close() closes the Mini App WebView.
 *   - Telegram.WebApp.expand() expands the Mini App to full height.
 *   - sendData() can only be called ONCE per Mini App session.  After calling
 *     it, the connection to the bot is established and the Mini App should
 *     close.
 *
 * =============================================================================
 */


// =============================================================================
//  CONFIGURATION
// =============================================================================

/**
 * YOUR MONETAG ZONE ID
 * --------------------
 * Replace "XXXXX" with your actual zone ID from the Monetag dashboard.
 *
 * This ID is used in two places:
 * 1. In index.html  ->  <script data-zone="XXXXX" data-sdk="show_XXXXX">
 * 2. Here           ->  To reference the global function: window["show_XXXXX"]
 *
 * THEY MUST MATCH.  If the IDs are different, the SDK won't work.
 *
 * Example:  If your zone ID is 987654, then:
 *   - In index.html:  data-zone="987654"  data-sdk="show_987654"
 *   - Here:           const ZONE_ID = "987654";
 */
const ZONE_ID = "XXXXX";  // <-- REPLACE with your Monetag zone ID

/**
 * The global function name created by the Monetag SDK.
 * Convention: "show_" + ZONE_ID.
 * We'll access it as window[AD_FUNCTION_NAME] to call it dynamically.
 */
const AD_FUNCTION_NAME = "show_" + ZONE_ID;


// =============================================================================
//  DOM ELEMENT REFERENCES
// =============================================================================

/**
 * Cache DOM element references for performance.
 * These are used throughout the script to show/hide overlays and update UI.
 */
const watchAdBtn      = document.getElementById("watchAdBtn");       // CTA button
const loadingOverlay  = document.getElementById("loadingOverlay");   // Loading spinner overlay
const successOverlay  = document.getElementById("successOverlay");   // Checkmark overlay
const errorMsg        = document.getElementById("errorMsg");         // Inline error message


// =============================================================================
//  TELEGRAM WEBAPP INITIALIZATION
// =============================================================================

/**
 * Initialize the Telegram WebApp SDK.
 *
 * Telegram.WebApp is injected by telegram-web-app.js (loaded in <head>).
 * It provides context about the user, the bot, and the current theme.
 *
 * .ready()  -> Tells Telegram that the Mini App has finished loading.
 *              Telegram uses this to remove the loading indicator.
 *
 * .expand() -> Expands the Mini App to fill the full screen height.
 *              By default, Mini Apps open at half-height.
 *              Expanding gives us more space for the card UI.
 *
 * .initDataUnsafe.user -> Contains info about the current user:
 *              { id, first_name, last_name, username, language_code }
 *              We use .id as the ymid for Monetag postback tracking.
 */
const tg = window.Telegram?.WebApp;

if (tg) {
    // Signal to Telegram that our Mini App is fully loaded and ready
    tg.ready();

    // Expand the Mini App to full-screen height for better UX
    tg.expand();

    console.log("[MiniApp] Telegram WebApp initialized successfully.");
    console.log("[MiniApp] User:", tg.initDataUnsafe?.user?.first_name || "unknown");
} else {
    // This happens when the page is opened outside of Telegram (e.g., in a browser).
    // The app will still work for testing, but sendData() won't be available.
    console.warn("[MiniApp] Telegram WebApp SDK not available - running outside Telegram?");
}

/**
 * Get the Telegram user ID for Monetag's ymid parameter.
 * This allows Monetag postbacks to include the user's Telegram ID,
 * enabling server-side reward verification if needed later.
 *
 * Falls back to "anonymous" if the user data isn't available
 * (e.g., when testing outside Telegram).
 */
const telegramUserId = tg?.initDataUnsafe?.user?.id?.toString() || "anonymous";
console.log("[MiniApp] Telegram User ID for ymid:", telegramUserId);


// =============================================================================
//  MONETAG AD PRELOADING
// =============================================================================

/**
 * Preload the Monetag ad in the background when the page loads.
 *
 * WHY PRELOAD?
 * When the user taps "Watch Ad", we want the ad to appear instantly.
 * Without preloading, there's a noticeable delay while the ad creative
 * is fetched from Monetag's servers.  Preloading downloads the ad
 * content in advance so it's ready to display immediately.
 *
 * HOW IT WORKS:
 * We call the SDK function with { type: 'preload' }.  This downloads
 * the ad materials but does NOT display them.  Later, when we call
 * the SDK without 'preload', it shows the already-cached ad instantly.
 *
 * TIMEOUT:
 * We set a 10-second timeout for preloading.  If the ad can't be
 * preloaded within 10 seconds (slow network, no fill), the promise
 * rejects and we continue without preloading.  The ad will still
 * work when triggered - it just might have a loading delay.
 *
 * ERROR HANDLING:
 * Preload failure is NOT critical.  We catch errors silently and
 * set a flag.  The "Watch Ad" button works regardless.
 */

let adPreloaded = false;  // Tracks whether preloading succeeded

/**
 * Attempt to preload the ad.
 * We wrap this in a function and call it immediately.
 * The preload runs asynchronously and doesn't block page rendering.
 */
function preloadAd() {
    // Check if the Monetag SDK function is available on the window object
    const showAd = window[AD_FUNCTION_NAME];

    if (typeof showAd !== "function") {
        console.warn("[MiniApp] Monetag SDK function not found. SDK may still be loading.");
        // Retry preloading after a short delay (SDK might not have loaded yet)
        setTimeout(preloadAd, 2000);
        return;
    }

    console.log("[MiniApp] Attempting to preload Monetag ad...");

    showAd({
        type: "preload",             // Preload mode - download but don't show
        ymid: telegramUserId,        // User identifier for postback tracking
        timeout: 10,                 // Max 10 seconds for preload to complete
    })
    .then(function() {
        adPreloaded = true;
        console.log("[MiniApp] Ad preloaded successfully! Ready for instant display.");
    })
    .catch(function(err) {
        adPreloaded = false;
        console.warn("[MiniApp] Ad preload failed (non-critical):", err?.message || err);
        // This is fine - the ad will still load when triggered, just with a delay
    });
}

// Start preloading as soon as the page loads
// Use a small delay to ensure the SDK script has finished executing
setTimeout(preloadAd, 1000);


// =============================================================================
//  UTILITY FUNCTIONS
// =============================================================================

/**
 * Shows the loading overlay (spinner + "Loading ad..." text).
 * Called when the user taps the button and we're waiting for the ad.
 */
function showLoading() {
    loadingOverlay.style.display = "flex";
}

/**
 * Hides the loading overlay.
 * Called when the ad finishes (success or failure).
 */
function hideLoading() {
    loadingOverlay.style.display = "none";
}

/**
 * Shows the success overlay (animated checkmark + "Ad complete!" text).
 * Called after the Monetag ad resolves successfully.
 */
function showSuccess() {
    successOverlay.style.display = "flex";
}

/**
 * Displays the inline error message below the button.
 * @param {string} message - The error text to display.
 */
function showError(message) {
    errorMsg.textContent = message;
    errorMsg.style.display = "block";
}

/**
 * Hides the inline error message.
 * Called when the user tries again (button re-enabled).
 */
function hideError() {
    errorMsg.style.display = "none";
}


// =============================================================================
//  MAIN AD FLOW  -  Button click handler
// =============================================================================

/**
 * Event listener for the "Watch Ad & Download" button.
 *
 * COMPLETE FLOW:
 * 1. Disable button to prevent double-taps.
 * 2. Hide any previous error message.
 * 3. Show loading overlay with spinner.
 * 4. Call the Monetag SDK to show a Rewarded Interstitial.
 * 5. On SUCCESS:
 *    a. Hide loading overlay.
 *    b. Show success overlay with animated checkmark.
 *    c. Wait 1.5 seconds for animation to play.
 *    d. Call Telegram.WebApp.sendData("ad_completed") to notify the bot.
 *    e. Call Telegram.WebApp.close() to close the Mini App.
 * 6. On FAILURE:
 *    a. Hide loading overlay.
 *    b. Show inline error message.
 *    c. Re-enable the button for retry.
 */
watchAdBtn.addEventListener("click", function() {

    // ── Step 1: Disable button to prevent double-taps ──
    // This prevents the user from accidentally triggering multiple ads.
    watchAdBtn.disabled = true;

    // ── Step 2: Clear any previous error ──
    hideError();

    // ── Step 3: Show loading state ──
    showLoading();

    // ── Step 4: Get the Monetag SDK function ──
    const showAd = window[AD_FUNCTION_NAME];

    // Safety check: Verify the SDK function exists
    if (typeof showAd !== "function") {
        hideLoading();
        showError(
            "Ad system is not ready. Please close this window and try again in a moment."
        );
        watchAdBtn.disabled = false;
        console.error("[MiniApp] Monetag SDK function '" + AD_FUNCTION_NAME + "' not found!");
        return;
    }

    console.log("[MiniApp] Triggering Monetag Rewarded Interstitial...");

    // ── Step 5: Call the Monetag SDK ──
    //
    // We call show_XXXXX() with type "end" (default).
    // "end" means the Promise resolves AFTER the user has watched and
    // CLOSED the ad.  This ensures we only reward users who fully
    // watched the ad.
    //
    // Parameters:
    //   ymid         : Telegram user ID for postback tracking.
    //   requestVar   : A label for this placement (useful for analytics
    //                  in the Monetag dashboard - you can track which
    //                  buttons/placements generate the most revenue).
    //
    showAd({
        ymid: telegramUserId,
        requestVar: "download_button",
    })
    .then(function(result) {
        // ══════════════════════════════════════════════════════════════
        //  AD COMPLETED SUCCESSFULLY
        // ══════════════════════════════════════════════════════════════
        //
        //  The user has watched the full ad.  The 'result' object
        //  contains information about the ad event:
        //    result.reward_event_type  -  "valued" or "not_valued"
        //    result.estimated_price    -  Approximate revenue (optional)
        //    result.zone_id            -  Which zone served the ad
        //
        //  Regardless of reward_event_type, we proceed with the download
        //  because the user has done their part (watched the ad).

        console.log("[MiniApp] Ad completed successfully!", result);

        // Hide loading overlay
        hideLoading();

        // Show success overlay with animated checkmark
        showSuccess();

        // ── Wait for the checkmark animation, then send data & close ──
        //
        // We delay 1.5 seconds so the user can see the success animation.
        // Then:
        //   sendData("ad_completed") -> Sends the string to the bot.
        //     The bot's web_app_data handler receives this and starts
        //     downloading the previously saved URL.
        //   close() -> Closes the Mini App WebView.
        //
        // NOTE: sendData() can only be called ONCE per session.
        //       After calling it, the Mini App should close.

        setTimeout(function() {
            if (tg) {
                try {
                    // Send the signal to the bot
                    tg.sendData("ad_completed");
                    console.log("[MiniApp] Sent 'ad_completed' to bot.");
                } catch (sendErr) {
                    console.error("[MiniApp] sendData failed:", sendErr);
                }

                // Close the Mini App after a brief moment
                setTimeout(function() {
                    tg.close();
                }, 500);
            } else {
                // Running outside Telegram (testing) - just log it
                console.log("[MiniApp] [TEST MODE] Would send 'ad_completed' and close.");
                alert("Test mode: Ad completed! In Telegram, data would be sent to the bot.");
            }
        }, 1500);  // 1.5 second delay for animation
    })
    .catch(function(error) {
        // ══════════════════════════════════════════════════════════════
        //  AD FAILED OR WAS UNAVAILABLE
        // ══════════════════════════════════════════════════════════════
        //
        //  Possible reasons:
        //  - No ad fill (Monetag has no ads for this user/region)
        //  - Network error during ad loading
        //  - User dismissed the ad before it completed
        //  - Zone misconfiguration
        //  - Ad was blocked by the user's device/network
        //
        //  We inform the user and let them retry.

        console.error("[MiniApp] Ad failed:", error?.message || error);

        // Hide loading overlay
        hideLoading();

        // Show user-friendly error message
        showError(
            "The ad couldn't load right now. Please wait a moment and try again. " +
            "If this keeps happening, close and reopen the app."
        );

        // Re-enable button so user can retry
        watchAdBtn.disabled = false;

        // ── Attempt to preload again for the next try ──
        // This way, if the user retries, the ad might be ready.
        setTimeout(preloadAd, 3000);
    });
});


// =============================================================================
//  THEME ADAPTATION (OPTIONAL ENHANCEMENT)
// =============================================================================

/**
 * Telegram provides theme parameters that match the user's current
 * Telegram theme (light/dark mode, accent colors, etc.).
 *
 * We can use these to make the Mini App feel more native.
 * This is optional - our gradient design looks good regardless.
 *
 * Available theme params (Telegram.WebApp.themeParams):
 *   bg_color, text_color, hint_color, link_color,
 *   button_color, button_text_color, secondary_bg_color,
 *   header_bg_color, accent_text_color, section_bg_color,
 *   section_header_text_color, subtitle_text_color,
 *   destructive_text_color
 */
if (tg && tg.themeParams) {
    // Log theme params for debugging
    console.log("[MiniApp] Telegram theme params:", JSON.stringify(tg.themeParams));

    // Example: You could adapt colors like this (uncomment if desired):
    // document.documentElement.style.setProperty('--primary', tg.themeParams.button_color);
}


// =============================================================================
//  BACK BUTTON HANDLER (OPTIONAL)
// =============================================================================

/**
 * Telegram Mini Apps can show a back button in the header.
 * When tapped, it fires the backButtonClicked event.
 * We use it to simply close the Mini App.
 */
if (tg) {
    tg.BackButton.show();
    tg.BackButton.onClick(function() {
        tg.close();
    });
}


// =============================================================================
//  CONSOLE LOG  -  Confirm script loaded
// =============================================================================

console.log("[MiniApp] script.js loaded successfully.");
console.log("[MiniApp] Zone ID:", ZONE_ID);
console.log("[MiniApp] Ad function name:", AD_FUNCTION_NAME);
console.log("[MiniApp] Waiting for user interaction...");
