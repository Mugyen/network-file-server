/** Copy text to the OS clipboard in both secure and non-secure contexts.
 *
 * navigator.clipboard requires a secure context (HTTPS or localhost);
 * HTTP-over-LAN (e.g., phone access) falls back to a hidden textarea +
 * execCommand, which still works there. Rejects only on the async
 * clipboard path (e.g., document not focused).
 */
export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}
