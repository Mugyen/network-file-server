import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownPreviewProps {
  content: string;
}

/**
 * Markdown preview with GitHub Flavored Markdown support.
 *
 * Renders tables, strikethrough, task lists, and autolinks via remark-gfm.
 * Manual typography styles applied (prose classes require @tailwindcss/typography).
 */
function MarkdownPreview({ content }: MarkdownPreviewProps) {
  return (
    <div className="prose dark:prose-invert max-w-none p-4 overflow-auto max-h-[75vh]">
      <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
    </div>
  );
}

export default MarkdownPreview;
