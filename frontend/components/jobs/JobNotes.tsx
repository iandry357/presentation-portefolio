 
'use client';

import { useState, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import {
  Bold, Italic, Underline as UnderlineIcon,
  Heading2, Heading3, List, ListOrdered,
  Minus, RemoveFormatting, Pencil, Save, Loader2,
} from 'lucide-react';
import { saveJobNotes } from '@/lib/api';

interface JobNotesProps {
  jobId: number;
  initialNotes: string | null;
  onNotesSaved?: (notes: string) => void;
}

const COLORS = [
  { label: 'Défaut',  value: 'inherit' },
  { label: 'Rouge',   value: '#ef4444' },
  { label: 'Orange',  value: '#f97316' },
  { label: 'Jaune',   value: '#eab308' },
  { label: 'Vert',    value: '#22c55e' },
  { label: 'Bleu',    value: '#3b82f6' },
  { label: 'Violet',  value: '#a855f7' },
  { label: 'Gris',    value: '#6b7280' },
];

export default function JobNotes({ jobId, initialNotes, onNotesSaved }: JobNotesProps) {
  const [editing, setEditing] = useState(!initialNotes);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit,
      Underline,
      TextStyle,
      Color,
    ],
    content: initialNotes || '<p></p>',
    editable: !initialNotes,
    editorProps: {
      attributes: {
        class: 'prose prose-sm dark:prose-invert max-w-none min-h-[120px] focus:outline-none',
      },
    },
  });

  const handleEdit = useCallback(() => {
    editor?.setEditable(true);
    setEditing(true);
    setSavedMessage(null);
  }, [editor]);

  const handleSave = useCallback(async () => {
    if (!editor) return;
    setSaving(true);
    try {
      const html = editor.getHTML();
      await saveJobNotes(jobId, html);
      editor.setEditable(false);
      setEditing(false);
      onNotesSaved?.(html);
      setSavedMessage('Notes sauvegardées');
      setTimeout(() => setSavedMessage(null), 3000);
    } catch {
      setSavedMessage('Erreur lors de la sauvegarde');
    } finally {
      setSaving(false);
    }
  }, [editor, jobId]);

  if (!editor) return null;

  return (
    <div className="space-y-3 pt-4">

      {/* Barre d'outils — visible uniquement en mode édition */}
      {editing && (
        <div className="flex flex-wrap items-center gap-1 p-2 bg-gray-50 dark:bg-gray-700/50 rounded-md border border-gray-200 dark:border-gray-600">

          {/* Gras */}
          <ToolbarButton
            active={editor.isActive('bold')}
            onClick={() => editor.chain().focus().toggleBold().run()}
            title="Gras"
          >
            <Bold className="w-4 h-4" />
          </ToolbarButton>

          {/* Italique */}
          <ToolbarButton
            active={editor.isActive('italic')}
            onClick={() => editor.chain().focus().toggleItalic().run()}
            title="Italique"
          >
            <Italic className="w-4 h-4" />
          </ToolbarButton>

          {/* Souligné */}
          <ToolbarButton
            active={editor.isActive('underline')}
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            title="Souligné"
          >
            <UnderlineIcon className="w-4 h-4" />
          </ToolbarButton>

          <Divider />

          {/* Titre H2 */}
          <ToolbarButton
            active={editor.isActive('heading', { level: 2 })}
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            title="Titre"
          >
            <Heading2 className="w-4 h-4" />
          </ToolbarButton>

          {/* Titre H3 */}
          <ToolbarButton
            active={editor.isActive('heading', { level: 3 })}
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            title="Sous-titre"
          >
            <Heading3 className="w-4 h-4" />
          </ToolbarButton>

          <Divider />

          {/* Liste à puces */}
          <ToolbarButton
            active={editor.isActive('bulletList')}
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            title="Liste à puces"
          >
            <List className="w-4 h-4" />
          </ToolbarButton>

          {/* Liste numérotée */}
          <ToolbarButton
            active={editor.isActive('orderedList')}
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            title="Liste numérotée"
          >
            <ListOrdered className="w-4 h-4" />
          </ToolbarButton>

          <Divider />

          {/* Séparateur */}
          <ToolbarButton
            active={false}
            onClick={() => editor.chain().focus().setHorizontalRule().run()}
            title="Séparateur"
          >
            <Minus className="w-4 h-4" />
          </ToolbarButton>

          <Divider />

          {/* Couleur du texte */}
          <div className="flex items-center gap-1">
            {COLORS.map(c => (
              <button
                key={c.value}
                title={c.label}
                onClick={() =>
                  c.value === 'inherit'
                    ? editor.chain().focus().unsetColor().run()
                    : editor.chain().focus().setColor(c.value).run()
                }
                className="w-5 h-5 rounded-full border border-gray-300 dark:border-gray-500 hover:scale-110 transition-transform"
                style={{ backgroundColor: c.value === 'inherit' ? '#e5e7eb' : c.value }}
              />
            ))}
          </div>

          <Divider />

          {/* Effacer le formatage */}
          <ToolbarButton
            active={false}
            onClick={() => editor.chain().focus().clearNodes().unsetAllMarks().run()}
            title="Effacer le formatage"
          >
            <RemoveFormatting className="w-4 h-4" />
          </ToolbarButton>
        </div>
      )}

      {/* Zone d'édition */}
      <div
        className={`rounded-md border px-4 py-3 text-sm transition-colors ${
          editing
            ? 'border-blue-300 dark:border-blue-600 bg-white dark:bg-gray-900'
            : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
        }`}
      >
        <EditorContent editor={editor} />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {savedMessage}
        </span>
        <div className="flex gap-2">
          {!editing ? (
            <button
              onClick={handleEdit}
              className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" />
              Modifier
            </button>
          ) : (
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
            >
              {saving
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Save className="w-3.5 h-3.5" />
              }
              Sauvegarder
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sous-composants internes ──────────────────────────────────────────────────

function ToolbarButton({
  children, active, onClick, title,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
  title: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={`p-1.5 rounded transition-colors ${
        active
          ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
          : 'text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
      }`}
    >
      {children}
    </button>
  );
}

function Divider() {
  return <span className="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-0.5" />;
}