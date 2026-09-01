document.getElementById('fillBtn').addEventListener('click', async () => {
  const jsonText = document.getElementById('jsonInput').value;
  const statusDiv = document.getElementById('status');
  
  if (!jsonText) {
    statusDiv.innerText = "Please paste the JSON first!";
    return;
  }

  try {
    const candidateData = JSON.parse(jsonText);
    
    // Get the active tab
    let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    // Execute the content script logic in the active tab
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js']
    }, () => {
      // Send the data to the content script
      chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM", data: candidateData }, (response) => {
        statusDiv.style.color = "#28a745";
        statusDiv.innerText = "✅ Form Filled Successfully!";
      });
    });
  } catch (e) {
    statusDiv.innerText = "Invalid JSON format! Please check the text.";
  }
});
