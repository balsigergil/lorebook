import { mergeAttributes, Node } from "@tiptap/core";

export type CalloutVariant = "info" | "success" | "warning" | "danger";

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    callout: {
      setCallout: (variant: CalloutVariant) => ReturnType;
      toggleCallout: (variant: CalloutVariant) => ReturnType;
    };
  }
}

const ICONS: Record<CalloutVariant, string> = {
  info: "fa-circle-info",
  success: "fa-circle-check",
  warning: "fa-triangle-exclamation",
  danger: "fa-circle-exclamation",
};

/** A highlighted block (hint) holding other blocks, rendered by the Python renderer too. */
export const Callout = Node.create({
  name: "callout",
  group: "block",
  content: "block+",
  defining: true,

  addAttributes() {
    return {
      variant: {
        default: "info",
        parseHTML: (element) => element.getAttribute("data-variant") ?? "info",
        renderHTML: (attributes) => ({ "data-variant": attributes.variant }),
      },
    };
  },

  parseHTML() {
    return [{ tag: "div[data-callout]" }];
  },

  renderHTML({ node, HTMLAttributes }) {
    const variant = (node.attrs.variant ?? "info") as CalloutVariant;
    return [
      "div",
      mergeAttributes(HTMLAttributes, { "data-callout": "", class: `callout callout-${variant}` }),
      ["i", { class: `callout-icon fa-solid ${ICONS[variant] ?? ICONS.info}`, contenteditable: "false" }],
      ["div", { class: "callout-content" }, 0],
    ];
  },

  addCommands() {
    return {
      setCallout:
        (variant) =>
        ({ commands }) =>
          commands.wrapIn(this.name, { variant }),
      toggleCallout:
        (variant) =>
        ({ editor, commands }) => {
          if (editor.isActive(this.name, { variant })) return commands.lift(this.name);
          if (editor.isActive(this.name)) return commands.updateAttributes(this.name, { variant });
          return commands.wrapIn(this.name, { variant });
        },
    };
  },
});
