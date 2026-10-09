import { useCallback, useEffect, useRef, useState } from "react";
import { EditorContent, useEditor, useEditorState, type Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
import { TaskItem, TaskList } from "@tiptap/extension-list";
import { Placeholder } from "@tiptap/extensions";
import type { EditorView } from "@tiptap/pm/view";

import { ApiError, saveDraft, upload } from "./api/client";
import { Callout, type CalloutVariant } from "./callout";

export interface EditorProps {
  translationId: number;
  collectionId: number;
  language: string;
  title: string;
  content: Record<string, unknown>;
  draftUpdatedAt: string;
  hasDraftChanges: boolean;
  isPublished: boolean;
  apiBase: string;
  strings: Record<string, string>;
}

type SaveState = "saved" | "changed" | "pending" | "saving" | "error";

const AUTOSAVE_DELAY = 800;
const PUBLISH_FORM_ID = "form-publishform";

function useStatusBadge(strings: Record<string, string>) {
  return useCallback(
    (state: SaveState) => {
      const element = document.getElementById("save-status");
      if (!element) return;
      element.dataset.state = state;
      element.textContent = strings[state] ?? state;
    },
    [strings],
  );
}

export function DocumentEditor(props: EditorProps) {
  const { strings } = props;
  const [title, setTitle] = useState(props.title);
  const titleRef = useRef(props.title);
  const timer = useRef<number | undefined>(undefined);
  const dirty = useRef(false);
  const saving = useRef<Promise<void> | null>(null);
  const editorRef = useRef<Editor | null>(null);
  const titleInput = useRef<HTMLTextAreaElement>(null);
  const setStatus = useStatusBadge(strings);

  const save = useCallback(async () => {
    const editor = editorRef.current;
    if (!editor || !dirty.current) return;
    if (saving.current) {
      await saving.current;
    }
    dirty.current = false;
    setStatus("saving");
    const run = saveDraft(props.translationId, {
      title: titleRef.current,
      content: editor.getJSON() as Record<string, unknown>,
    })
      .then(() => {
        if (!dirty.current) setStatus(props.isPublished ? "changed" : "saved");
      })
      .catch((error: unknown) => {
        dirty.current = true;
        setStatus("error");
        console.error(error);
        window.clearTimeout(timer.current);
        timer.current = window.setTimeout(() => void save(), 5000);
      })
      .finally(() => {
        saving.current = null;
      });
    saving.current = run;
    await run;
  }, [props.translationId, props.isPublished, setStatus]);

  const schedule = useCallback(() => {
    dirty.current = true;
    setStatus("pending");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void save(), AUTOSAVE_DELAY);
  }, [save, setStatus]);

  const uploadFiles = useCallback(
    async (files: File[], view?: EditorView, position?: number) => {
      const editor = editorRef.current;
      if (!editor) return;
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        try {
          const media = await upload(props.collectionId, form);
          const node = { type: "image", attrs: { src: media.url, alt: file.name.replace(/\.[^.]+$/, "") } };
          if (view && position !== undefined) {
            editor.chain().insertContentAt(position, node).run();
          } else {
            editor.chain().focus().insertContent(node).run();
          }
        } catch (error) {
          const detail = error instanceof ApiError ? String(error.detail) : String(error);
          window.Bloum?.Toast.danger(strings.uploadFailed, detail);
        }
      }
    },
    [props.collectionId, strings.uploadFailed],
  );

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
        link: { openOnClick: false, autolink: true, defaultProtocol: "https" },
      }),
      Image.configure({ allowBase64: false }),
      TableKit.configure({ table: { resizable: false } }),
      TaskList,
      TaskItem.configure({ nested: true }),
      Callout,
      Placeholder.configure({ placeholder: strings.placeholder }),
    ],
    content: props.content,
    editorProps: {
      attributes: { class: "prose prose-editor", lang: props.language, spellcheck: "true" },
      handlePaste(view, event) {
        const files = Array.from(event.clipboardData?.files ?? []).filter((file) => file.type.startsWith("image/"));
        if (!files.length) return false;
        void uploadFiles(files);
        return true;
      },
      handleDrop(view, event) {
        const files = Array.from(event.dataTransfer?.files ?? []).filter((file) => file.type.startsWith("image/"));
        if (!files.length) return false;
        const position = view.posAtCoords({ left: event.clientX, top: event.clientY })?.pos;
        void uploadFiles(files, view, position);
        return true;
      },
    },
    onUpdate: () => schedule(),
    immediatelyRender: true,
  });
  editorRef.current = editor;

  // Publishing sends the current state along with the form, so nothing typed
  // since the last autosave is lost.
  useEffect(() => {
    const onConfig = (event: Event) => {
      const ctx = (event as CustomEvent).detail?.ctx;
      const source = ctx?.sourceElement as HTMLElement | undefined;
      if (!source?.closest(`#${PUBLISH_FORM_ID}`) || !editorRef.current) return;
      window.clearTimeout(timer.current);
      dirty.current = false;
      ctx.request.body.set("title", titleRef.current);
      ctx.request.body.set("content", JSON.stringify(editorRef.current.getJSON()));
    };
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (dirty.current || saving.current) {
        void save();
        event.preventDefault();
      }
    };
    document.addEventListener("htmx:config:request", onConfig);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      document.removeEventListener("htmx:config:request", onConfig);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [save]);

  useEffect(() => {
    const input = titleInput.current;
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  }, [title]);

  return (
    <div className="document-editor">
      <Toolbar editor={editor} strings={strings} onPickImages={uploadFiles} />
      <div className="document-page">
        <textarea
          ref={titleInput}
          className="document-title"
          value={title}
          rows={1}
          placeholder={strings.titlePlaceholder}
          aria-label={strings.title}
          onChange={(event) => {
            const value = event.target.value.replace(/\n/g, " ");
            setTitle(value);
            titleRef.current = value;
            schedule();
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              editor?.commands.focus("start");
            }
          }}
        />
        <EditorContent editor={editor} className="document-content" />
      </div>
    </div>
  );
}

interface ToolbarProps {
  editor: Editor | null;
  strings: Record<string, string>;
  onPickImages: (files: File[]) => void;
}

function Toolbar({ editor, strings, onPickImages }: ToolbarProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const state = useEditorState({
    editor,
    selector: ({ editor: current }) => {
      if (!current) return null;
      return {
        bold: current.isActive("bold"),
        italic: current.isActive("italic"),
        underline: current.isActive("underline"),
        strike: current.isActive("strike"),
        code: current.isActive("code"),
        link: current.isActive("link"),
        bulletList: current.isActive("bulletList"),
        orderedList: current.isActive("orderedList"),
        taskList: current.isActive("taskList"),
        blockquote: current.isActive("blockquote"),
        codeBlock: current.isActive("codeBlock"),
        table: current.isActive("table"),
        callout: current.isActive("callout"),
        block: current.isActive("heading", { level: 2 })
          ? "h2"
          : current.isActive("heading", { level: 3 })
            ? "h3"
            : current.isActive("heading", { level: 4 })
              ? "h4"
              : "p",
        canUndo: current.can().undo(),
        canRedo: current.can().redo(),
      };
    },
  });
  if (!editor || !state) return null;

  const chain = () => editor.chain().focus();

  const setLink = () => {
    const previous = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt(strings.linkPrompt, previous ?? "https://");
    if (url === null) return;
    if (url.trim() === "") {
      chain().extendMarkRange("link").unsetLink().run();
      return;
    }
    chain().extendMarkRange("link").setLink({ href: url.trim() }).run();
  };

  const insert = (value: string) => {
    if (value.startsWith("callout-")) {
      chain()
        .toggleCallout(value.replace("callout-", "") as CalloutVariant)
        .run();
    } else if (value === "table") {
      chain().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
    } else if (value === "hr") {
      chain().setHorizontalRule().run();
    } else if (value === "image") {
      fileInput.current?.click();
    }
  };

  const button = (label: string, icon: string, active: boolean, run: () => void, disabled = false) => (
    <button
      type="button"
      className={`toolbar-button${active ? " is-active" : ""}`}
      title={label}
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onMouseDown={(event) => event.preventDefault()}
      onClick={run}
    >
      <i className={`fa-solid ${icon}`} />
    </button>
  );

  return (
    <div className="editor-toolbar" role="toolbar" aria-label={strings.toolbar}>
      <div className="toolbar-section">
        {button(strings.undo, "fa-rotate-left", false, () => chain().undo().run(), !state.canUndo)}
        {button(strings.redo, "fa-rotate-right", false, () => chain().redo().run(), !state.canRedo)}
      </div>
      <div className="toolbar-section">
        <select
          className="toolbar-select"
          aria-label={strings.blockType}
          value={state.block}
          onChange={(event) => {
            const value = event.target.value;
            if (value === "p") chain().setParagraph().run();
            else chain().setHeading({ level: Number(value.slice(1)) as 2 | 3 | 4 }).run();
          }}
        >
          <option value="p">{strings.paragraph}</option>
          <option value="h2">{strings.heading2}</option>
          <option value="h3">{strings.heading3}</option>
          <option value="h4">{strings.heading4}</option>
        </select>
      </div>
      <div className="toolbar-section">
        {button(strings.bold, "fa-bold", state.bold, () => chain().toggleBold().run())}
        {button(strings.italic, "fa-italic", state.italic, () => chain().toggleItalic().run())}
        {button(strings.underline, "fa-underline", state.underline, () => chain().toggleUnderline().run())}
        {button(strings.strike, "fa-strikethrough", state.strike, () => chain().toggleStrike().run())}
        {button(strings.code, "fa-code", state.code, () => chain().toggleCode().run())}
        {button(strings.link, "fa-link", state.link, setLink)}
      </div>
      <div className="toolbar-section">
        {button(strings.bulletList, "fa-list-ul", state.bulletList, () => chain().toggleBulletList().run())}
        {button(strings.orderedList, "fa-list-ol", state.orderedList, () => chain().toggleOrderedList().run())}
        {button(strings.taskList, "fa-list-check", state.taskList, () => chain().toggleTaskList().run())}
        {button(strings.quote, "fa-quote-left", state.blockquote, () => chain().toggleBlockquote().run())}
        {button(strings.codeBlock, "fa-file-code", state.codeBlock, () => chain().toggleCodeBlock().run())}
      </div>
      <div className="toolbar-section">
        {button(strings.image, "fa-image", false, () => fileInput.current?.click())}
        <select
          className="toolbar-select"
          aria-label={strings.insert}
          value=""
          onChange={(event) => {
            insert(event.target.value);
            event.target.value = "";
          }}
        >
          <option value="" disabled>
            {strings.insert}
          </option>
          <option value="callout-info">{strings.calloutInfo}</option>
          <option value="callout-success">{strings.calloutSuccess}</option>
          <option value="callout-warning">{strings.calloutWarning}</option>
          <option value="callout-danger">{strings.calloutDanger}</option>
          <option value="table">{strings.table}</option>
          <option value="hr">{strings.divider}</option>
        </select>
        <input
          ref={fileInput}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp,image/avif"
          multiple
          hidden
          onChange={(event) => {
            onPickImages(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
      </div>
      {state.table && (
        <div className="toolbar-section">
          {button(strings.addRow, "fa-grip-lines", false, () => chain().addRowAfter().run())}
          {button(strings.addColumn, "fa-grip-lines-vertical", false, () => chain().addColumnAfter().run())}
          {button(strings.deleteRow, "fa-minus", false, () => chain().deleteRow().run())}
          {button(strings.deleteColumn, "fa-delete-left", false, () => chain().deleteColumn().run())}
          {button(strings.deleteTable, "fa-table-cells-large", false, () => chain().deleteTable().run())}
        </div>
      )}
    </div>
  );
}
