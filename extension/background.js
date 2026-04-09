console.log("AllInOnePolyglotAIJDK DevTools Bridge loaded");

chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  if (message.action === "executeJS") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || !tabs[0]) {
        sendResponse({ success: false, error: "No active tab found" });
        return;
      }
      const tabId = tabs[0].id;
      chrome.debugger.attach({ tabId }, "1.3", () => {
        if (chrome.runtime.lastError) {
          sendResponse({ success: false, error: chrome.runtime.lastError.message });
          return;
        }
        chrome.debugger.sendCommand(
          { tabId },
          "Runtime.evaluate",
          { expression: message.code, returnByValue: true },
          (result) => {
            const cmdError = chrome.runtime.lastError;
            chrome.debugger.detach({ tabId }, () => {
              if (cmdError) {
                sendResponse({ success: false, error: cmdError.message });
              } else {
                sendResponse({ success: true, result: result });
              }
            });
          }
        );
      });
    });
    return true; // Keep channel open for async response
  }
});
