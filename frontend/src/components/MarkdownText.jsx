import React from 'react';

/**
 * Parses inline markdown tokens:
 * - Bold: **text** or __text__ -> <strong>
 * - Italic: *text* or _text_ -> <em>
 * - Inline code: `code` -> <code>
 * - Links: [text](https://...) -> <a ...>
 */
function parseInlineMarkdown(text) {
  if (typeof text !== 'string' || !text) return text || null;

  // Regex matching inline tokens.
  // Using word boundary check for _ to prevent touching underscores in filenames or identifiers.
  const tokenRegex = /(`[^`]+`|\*\*(?:[^*]|\*[^*])+\*\*|__(?:[^_]|_[^_])+__|\*(?:[^*])+\*|(?<!\w)_(?:[^_])+_(?!\w)|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g;

  const parts = text.split(tokenRegex);

  return parts.map((part, i) => {
    if (!part) return null;

    // Inline code: `code`
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return (
        <code key={i} className="md-code">
          {part.slice(1, -1)}
        </code>
      );
    }

    // Bold: **text** or __text__
    if (
      (part.startsWith('**') && part.endsWith('**') && part.length >= 4) ||
      (part.startsWith('__') && part.endsWith('__') && part.length >= 4)
    ) {
      const inner = part.slice(2, -2);
      return (
        <strong key={i} className="md-strong">
          {parseInlineMarkdown(inner)}
        </strong>
      );
    }

    // Italic: *text* or _text_
    if (
      (part.startsWith('*') && part.endsWith('*') && part.length >= 2) ||
      (part.startsWith('_') && part.endsWith('_') && part.length >= 2)
    ) {
      const inner = part.slice(1, -1);
      return (
        <em key={i} className="md-em">
          {parseInlineMarkdown(inner)}
        </em>
      );
    }

    // Link: [text](url)
    const linkMatch = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (linkMatch) {
      return (
        <a
          key={i}
          href={linkMatch[2]}
          target="_blank"
          rel="noopener noreferrer"
          className="md-link"
        >
          {linkMatch[1]}
        </a>
      );
    }

    return part;
  });
}

/**
 * Parses block markdown: headings, bullet lists, ordered lists, code blocks, paragraphs.
 */
function parseBlockMarkdown(text) {
  if (typeof text !== 'string' || !text) return [];

  const lines = text.split(/\r?\n/);
  const blocks = [];
  let currentList = null; // { type: 'ul' | 'ol', items: [] }
  let currentParagraph = [];
  let inCodeBlock = false;
  let codeLines = [];
  let codeLang = '';

  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      blocks.push({ type: 'p', text: currentParagraph.join('\n') });
      currentParagraph = [];
    }
  };

  const flushList = () => {
    if (currentList) {
      blocks.push(currentList);
      currentList = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Fenced code blocks
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        blocks.push({ type: 'code', code: codeLines.join('\n'), lang: codeLang });
        codeLines = [];
        codeLang = '';
        inCodeBlock = false;
      } else {
        flushParagraph();
        flushList();
        inCodeBlock = true;
        codeLang = trimmed.slice(3).trim();
        codeLines = [];
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(rawLine);
      continue;
    }

    // Empty lines trigger block boundary
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    // Headings
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      blocks.push({
        type: 'heading',
        level: headingMatch[1].length,
        text: headingMatch[2],
      });
      continue;
    }

    // Bullet lists (- item, * item, • item)
    const ulMatch = trimmed.match(/^[-*•]\s+(.*)$/);
    if (ulMatch) {
      flushParagraph();
      if (!currentList || currentList.type !== 'ul') {
        flushList();
        currentList = { type: 'ul', items: [] };
      }
      currentList.items.push(ulMatch[1]);
      continue;
    }

    // Ordered lists (1. item)
    const olMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (olMatch) {
      flushParagraph();
      if (!currentList || currentList.type !== 'ol') {
        flushList();
        currentList = { type: 'ol', items: [] };
      }
      currentList.items.push(olMatch[2]);
      continue;
    }

    // Standard paragraph line
    flushList();
    currentParagraph.push(trimmed);
  }

  if (inCodeBlock && codeLines.length > 0) {
    blocks.push({ type: 'code', code: codeLines.join('\n'), lang: codeLang });
  }

  flushParagraph();
  flushList();
  return blocks;
}

/**
 * Zero-dependency Markdown renderer for React.
 *
 * Props:
 * - text: string containing markdown text
 * - inline: boolean. If true, only parses inline formatting and wraps in span/fragment.
 * - className: optional CSS class for container
 */
export default function MarkdownText({ text, inline = false, className = '' }) {
  if (!text || typeof text !== 'string') return null;

  if (inline) {
    return <span className={`md-inline ${className}`}>{parseInlineMarkdown(text)}</span>;
  }

  const blocks = parseBlockMarkdown(text);

  // If there is only a single paragraph with a single line, render directly without extra wrapper
  if (blocks.length === 1 && blocks[0].type === 'p' && !blocks[0].text.includes('\n')) {
    return <span className={`md-inline ${className}`}>{parseInlineMarkdown(blocks[0].text)}</span>;
  }

  return (
    <div className={`md-block ${className}`}>
      {blocks.map((block, idx) => {
        switch (block.type) {
          case 'heading': {
            const HeadingTag = `h${Math.min(block.level + 2, 6)}`;
            return (
              <HeadingTag key={idx} className="md-heading">
                {parseInlineMarkdown(block.text)}
              </HeadingTag>
            );
          }
          case 'ul':
            return (
              <ul key={idx} className="md-ul">
                {block.items.map((item, itemIdx) => (
                  <li key={itemIdx} className="md-li">
                    {parseInlineMarkdown(item)}
                  </li>
                ))}
              </ul>
            );
          case 'ol':
            return (
              <ol key={idx} className="md-ol">
                {block.items.map((item, itemIdx) => (
                  <li key={itemIdx} className="md-li">
                    {parseInlineMarkdown(item)}
                  </li>
                ))}
              </ol>
            );
          case 'code':
            return (
              <pre key={idx} className="md-pre">
                <code className="md-code-block">{block.code}</code>
              </pre>
            );
          case 'p':
          default:
            return (
              <p key={idx} className="md-p">
                {parseInlineMarkdown(block.text)}
              </p>
            );
        }
      })}
    </div>
  );
}
