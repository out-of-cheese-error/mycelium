// Mycelium Content Script - Extracts page content

(function () {
    // Listen for messages from the extension
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === 'getPageContent') {
            const content = extractPageContent();
            sendResponse({
                success: true,
                content: content.text,
                title: document.title,
                url: window.location.href,
                length: content.text.length
            });
        }
        return true;
    });

    function extractPageContent() {
        // Clone the document to avoid modifying the actual page
        const clone = document.body.cloneNode(true);

        // Remove scripts, styles, nav, footer, etc.
        const elementsToRemove = clone.querySelectorAll(
            'script, style, nav, footer, header, aside, iframe, noscript, ' +
            '[role="navigation"], [role="banner"], [role="contentinfo"], ' +
            '.sidebar, .nav, .menu, .footer, .header, .advertisement, .ads'
        );
        elementsToRemove.forEach(el => el.remove());

        // Get text content
        let text = clone.innerText || clone.textContent || '';

        // Clean up whitespace
        text = text
            .split('\n')
            .map(line => line.trim())
            .filter(line => line.length > 0)
            .join('\n');

        // Remove excessive blank lines
        text = text.replace(/\n{3,}/g, '\n\n');

        return { text };
    }
})();
