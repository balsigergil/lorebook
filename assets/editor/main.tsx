import { createRoot } from "react-dom/client";

import { configure } from "./api/client";
import { DocumentEditor, type EditorProps } from "./DocumentEditor";
import "./editor.css";

function csrfToken(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "";
}

function mount() {
  const root = document.getElementById("editor-root");
  if (!root) return;
  const propsElement = document.getElementById(root.dataset.props ?? "editor-props");
  const props = JSON.parse(propsElement?.textContent ?? "{}") as EditorProps;
  configure({ baseUrl: props.apiBase, csrfToken });
  createRoot(root).render(<DocumentEditor {...props} />);
}

mount();
