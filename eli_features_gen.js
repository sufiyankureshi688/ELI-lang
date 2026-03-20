const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  TabStopType, TabStopPosition, PageNumber, TableOfContents,
  Header, Footer, PageBreak, VerticalAlign
} = require('docx');
const fs = require('fs');

// ─────────────────────────────────────────────────────────────────
// DESIGN TOKENS
// Typography-first. One accent. No decoration.
// Inspired by Linear / Stripe docs philosophy:
// font weight + size do the hierarchy work, not color.
// ─────────────────────────────────────────────────────────────────

const F = {
  prose: 'Georgia',        // warm serif for body — readable, slightly editorial
  ui:    'Trebuchet MS',   // clean, slightly technical sans for labels
  mono:  'Courier New',    // monospace — weight and presence
};

const C = {
  ink:      '0D0D0D',   // near-black for main text
  deep:     '1A1A2E',   // deep navy for section headings
  mid:      '4A4A4A',   // secondary text
  muted:    '9A9A9A',   // labels, file names, notes
  rule:     'E0E0E0',   // thin rules
  codeBg:   '161B22',   // GitHub dark — familiar to engineers
  codeText: 'C9D1D9',   // GitHub dark text
  synBg:    '0D1117',   // even darker for syntax lines — creates contrast hierarchy
  synText:  '79C0FF',   // blue-ish — syntax highlighted feel
  white:    'FFFFFF',
  indexBg:  'F8F8F8',   // very faint for index table
};

const pt = n => n * 2;

// ─────────────────────────────────────────────────────────────────
// PRIMITIVES
// ─────────────────────────────────────────────────────────────────

const noBorder = { style: BorderStyle.NONE, size: 0, color: C.white };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

const thinRule = (color = C.rule) => ({
  style: BorderStyle.SINGLE, size: 4, color, space: 1
});

const prose = (text, opts = {}) =>
  new TextRun({ text, font: F.prose, size: pt(10.5), color: C.ink, ...opts });

const ui = (text, opts = {}) =>
  new TextRun({ text, font: F.ui, size: pt(9), color: C.muted, ...opts });

const mono = (text, opts = {}) =>
  new TextRun({ text, font: F.mono, size: pt(9.5), color: C.codeText, ...opts });

const sp = (before = 0, after = 0) =>
  new Paragraph({ children: [], spacing: { before, after } });

// ─────────────────────────────────────────────────────────────────
// DARK CODE BLOCK
// ─────────────────────────────────────────────────────────────────

function codeBlock(lines, bg = C.codeBg, textColor = C.codeText) {
  if (typeof lines === 'string') lines = lines.split('\n');
  return new Table({
    width: { size: 6200, type: WidthType.DXA },
    columnWidths: [6200],
    rows: [new TableRow({
      children: [new TableCell({
        shading: { fill: bg, type: ShadingType.CLEAR },
        borders: noBorders,
        margins: { top: 160, bottom: 160, left: 240, right: 240 },
        children: lines.map(l => new Paragraph({
          spacing: { before: 18, after: 18 },
          children: [new TextRun({
            text: l === '' ? ' ' : l,
            font: F.mono,
            size: pt(9.5),
            color: textColor,
          })],
        })),
      })],
    })],
  });
}

// Syntax strip — slightly different bg and color to distinguish from example
function syntaxBlock(lines) {
  if (typeof lines === 'string') lines = [lines];
  return new Table({
    width: { size: 6200, type: WidthType.DXA },
    columnWidths: [6200],
    rows: [new TableRow({
      children: [new TableCell({
        shading: { fill: C.synBg, type: ShadingType.CLEAR },
        borders: noBorders,
        margins: { top: 120, bottom: 120, left: 240, right: 240 },
        children: lines.map(l => new Paragraph({
          spacing: { before: 16, after: 16 },
          children: [new TextRun({
            text: l === '' ? ' ' : l,
            font: F.mono,
            size: pt(10),
            bold: true,
            color: C.synText,
          })],
        })),
      })],
    })],
  });
}

// ─────────────────────────────────────────────────────────────────
// TWO-COLUMN FEATURE ENTRY
// Left col: name + meta (narrow, fixed)
// Right col: syntax + description + example
// This is the core layout decision — reference-book style
// ─────────────────────────────────────────────────────────────────

const LEFT_W  = 2000;  // DXA  ~1.4 inches
const RIGHT_W = 6200;  // DXA  ~4.3 inches
const GAP_W   =  160;  // DXA  small gutter
const TOTAL_W = LEFT_W + GAP_W + RIGHT_W; // = 8360

function featureEntry({ name, file, syntax, description, example, note }) {
  const syntaxLines = Array.isArray(syntax) ? syntax : [syntax];

  // ── LEFT COLUMN ──────────────────────────────────────────────
  const leftChildren = [
    sp(0, 60),
    new Paragraph({
      spacing: { before: 0, after: 80 },
      children: [new TextRun({
        text: name,
        font: F.ui,
        size: pt(10.5),
        bold: true,
        color: C.deep,
      })],
    }),
    new Paragraph({
      spacing: { before: 0, after: 0 },
      children: [new TextRun({
        text: file,
        font: F.mono,
        size: pt(8.5),
        color: C.muted,
        italics: true,
      })],
    }),
  ];

  // ── RIGHT COLUMN ─────────────────────────────────────────────
  const rightChildren = [
    // Syntax
    syntaxBlock(syntaxLines),
    sp(100, 0),

    // Description
    new Paragraph({
      spacing: { before: 0, after: note ? 60 : 100 },
      children: [new TextRun({
        text: description,
        font: F.prose,
        size: pt(10.5),
        color: C.ink,
      })],
    }),

    // Note
    ...(note ? [
      new Paragraph({
        spacing: { before: 0, after: 80 },
        indent: { left: 160 },
        border: { left: { style: BorderStyle.SINGLE, size: 8, color: C.muted, space: 10 } },
        children: [
          new TextRun({ text: 'Note  ', font: F.ui, size: pt(8.5), bold: true, color: C.muted, allCaps: true }),
          new TextRun({ text: note, font: F.prose, size: pt(9.5), color: C.mid, italics: true }),
        ],
      }),
    ] : []),

    // Example label
    new Paragraph({
      spacing: { before: 0, after: 40 },
      children: [new TextRun({
        text: 'EXAMPLE',
        font: F.ui,
        size: pt(7.5),
        bold: true,
        color: C.muted,
        allCaps: true,
        characterSpacing: 80,
      })],
    }),

    // Example code
    codeBlock(example.split('\n')),
    sp(200, 0),
  ];

  // ── ASSEMBLE ROW ─────────────────────────────────────────────
  return new Table({
    width: { size: TOTAL_W, type: WidthType.DXA },
    columnWidths: [LEFT_W, GAP_W, RIGHT_W],
    rows: [new TableRow({
      children: [
        // Left
        new TableCell({
          borders: noBorders,
          shading: { fill: C.white, type: ShadingType.CLEAR },
          margins: { top: 0, bottom: 0, left: 0, right: 0 },
          verticalAlign: VerticalAlign.TOP,
          width: { size: LEFT_W, type: WidthType.DXA },
          children: leftChildren,
        }),
        // Gutter
        new TableCell({
          borders: noBorders,
          shading: { fill: C.white, type: ShadingType.CLEAR },
          margins: { top: 0, bottom: 0, left: 0, right: 0 },
          width: { size: GAP_W, type: WidthType.DXA },
          children: [sp(0, 0)],
        }),
        // Right
        new TableCell({
          borders: noBorders,
          shading: { fill: C.white, type: ShadingType.CLEAR },
          margins: { top: 0, bottom: 0, left: 0, right: 0 },
          verticalAlign: VerticalAlign.TOP,
          width: { size: RIGHT_W, type: WidthType.DXA },
          children: rightChildren,
        }),
      ],
    })],
  });
}

// ─────────────────────────────────────────────────────────────────
// SECTION HEADING
// Big, dark, typographic weight — no background, no box
// ─────────────────────────────────────────────────────────────────

function sectionHeading(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 640, after: 0 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.deep, space: 6 } },
    children: [new TextRun({
      text: text,
      font: F.ui,
      size: pt(13),
      bold: true,
      color: C.deep,
      characterSpacing: 40,
    })],
  });
}

// ─────────────────────────────────────────────────────────────────
// INDEX TABLE
// Flat, scannable — feature name | syntax | file | section
// ─────────────────────────────────────────────────────────────────

function buildIndex(features) {
  const HDR_BG = C.deep;
  const ROW_ALT = 'F5F5F5';
  const colW = [2000, 3400, 1600, 1360]; // sums to 8360

  const hdrBorder = { style: BorderStyle.NONE, size: 0, color: HDR_BG };
  const cellBorder = { style: BorderStyle.SINGLE, size: 2, color: C.rule };
  const cellBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };

  // Header row
  const hdrRow = new TableRow({
    children: ['Feature', 'Syntax', 'File', 'Section'].map((h, ci) =>
      new TableCell({
        shading: { fill: HDR_BG, type: ShadingType.CLEAR },
        borders: { top: hdrBorder, bottom: hdrBorder, left: hdrBorder, right: hdrBorder },
        margins: { top: 100, bottom: 100, left: 120, right: 120 },
        width: { size: colW[ci], type: WidthType.DXA },
        children: [new Paragraph({
          spacing: { before: 0, after: 0 },
          children: [new TextRun({
            text: h,
            font: F.ui,
            size: pt(9),
            bold: true,
            color: C.white,
          })],
        })],
      })
    ),
  });

  let currentSection = '';
  let rowIdx = 0;
  const dataRows = [];

  features.forEach(f => {
    if (f.section) {
      currentSection = f.section;
      return;
    }
    const isAlt = rowIdx % 2 === 1;
    const bg = isAlt ? ROW_ALT : C.white;
    const syntaxLines = Array.isArray(f.syntax) ? f.syntax : [f.syntax];

    dataRows.push(new TableRow({
      children: [
        // Feature name
        new TableCell({
          shading: { fill: bg, type: ShadingType.CLEAR },
          borders: cellBorders,
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: colW[0], type: WidthType.DXA },
          children: [new Paragraph({
            spacing: { before: 0, after: 0 },
            children: [new TextRun({
              text: f.name,
              font: F.ui,
              size: pt(9.5),
              bold: true,
              color: C.deep,
            })],
          })],
        }),
        // Syntax (first line only for space)
        new TableCell({
          shading: { fill: bg, type: ShadingType.CLEAR },
          borders: cellBorders,
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: colW[1], type: WidthType.DXA },
          children: syntaxLines.map(s => new Paragraph({
            spacing: { before: 0, after: 0 },
            children: [new TextRun({
              text: s,
              font: F.mono,
              size: pt(8.5),
              color: C.mid,
            })],
          })),
        }),
        // File
        new TableCell({
          shading: { fill: bg, type: ShadingType.CLEAR },
          borders: cellBorders,
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: colW[2], type: WidthType.DXA },
          children: [new Paragraph({
            spacing: { before: 0, after: 0 },
            children: [new TextRun({
              text: f.file,
              font: F.mono,
              size: pt(8.5),
              color: C.muted,
              italics: true,
            })],
          })],
        }),
        // Section
        new TableCell({
          shading: { fill: bg, type: ShadingType.CLEAR },
          borders: cellBorders,
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          width: { size: colW[3], type: WidthType.DXA },
          children: [new Paragraph({
            spacing: { before: 0, after: 0 },
            children: [new TextRun({
              text: currentSection,
              font: F.ui,
              size: pt(8.5),
              color: C.muted,
            })],
          })],
        }),
      ],
    }));
    rowIdx++;
  });

  return new Table({
    width: { size: TOTAL_W, type: WidthType.DXA },
    columnWidths: colW,
    rows: [hdrRow, ...dataRows],
  });
}

// ─────────────────────────────────────────────────────────────────
// FEATURES DATA
// ─────────────────────────────────────────────────────────────────

const features = [

  { section: 'Core' },

  {
    name: 'Variable Assignment',
    file: 'assign.kw',
    syntax: '?name = *expr',
    description: 'Allocates a unique memory address for name on first use, then stores the result of expr there. Re-assigning the same name reuses the same address for the entire program lifetime.',
    example: `x = 42\ny = 3 4 A       # y = 7\nz = @ x @ y s   # z = x - y`,
  },

  {
    name: 'Variable Read',
    file: 'read.kw',
    syntax: '@ ?name',
    description: 'Pushes the current value of name onto the stack. Expands to the address followed by F (load). Used inside any expression wherever a value is needed.',
    example: `x = 10\ny = @ x @ x M   # y = x * x = 100\nprint @ y`,
  },

  {
    name: 'Print Integer',
    file: 'print.kw',
    syntax: 'print *expr',
    description: 'Evaluates expr and prints the integer result followed by a newline. Expands to: expr P',
    example: `print 42\nprint @ x\nprint @ a @ b A   # print a + b`,
  },

  { section: 'Control Flow' },

  {
    name: 'Conditional',
    file: 'if.kw',
    syntax: [
      'if *cond : **body endif',
      'if *cond : **body else : **alt endif',
    ],
    description: 'Evaluates cond. If non-zero, executes body. With else, executes alt when cond is zero. Generates unique labels per call. Nests to any depth inside any construct.',
    example: `if @ x 0 G :\n  print @ x\nendif\n\nif @ x @ y E :\n  print 1\nelse :\n  print 0\nendif`,
  },

  {
    name: 'While Loop',
    file: 'while.kw',
    syntax: 'while *cond : **body endwhile',
    description: 'Evaluates cond before each iteration. Exits when cond is zero. Nests to any depth. Both while and endwhile track nesting so inner loops never corrupt outer loop control flow.',
    example: `i = 0\nwhile @ i 10 L :\n  print @ i\n  i++\nendwhile`,
  },

  {
    name: 'For Loop',
    file: '(natural syntax)',
    syntax: 'for ?var from *start to *end : **body endfor',
    description: 'Counted loop. var iterates from start up to but not including end. Expands to a while loop — var is allocated as a normal variable and persists after the loop.',
    example: `total = 0\nfor i from 0 to 5 :\n  total += @ i\nendfor\nprint @ total   # 10`,
  },

  {
    name: 'Match',
    file: 'match.kw',
    syntax: [
      'match *expr : case *val : **body endcase ... endmatch',
      'match *expr : case *val : **body endcase ... else : **alt endmatch',
    ],
    description: 'Compares expr against each case value using equality (E opcode). Executes the first matching body. Optional else catches anything unmatched. Expands recursively — each case becomes a nested if/else chain.',
    example: `match @ code :\n  case 1 : print 10 endcase\n  case 2 : print 20 endcase\n  else :   print 99\nendmatch`,
  },

  { section: 'Syntactic Sugar' },

  {
    name: 'Increment / Decrement',
    file: '(natural syntax)',
    syntax: ['x++', 'x--'],
    description: 'Increments or decrements variable x by 1 in place. Expands to: x = @ x 1 A and x = @ x 1 s respectively.',
    example: `i = 0\ni++   # i = 1\ni--   # i = 0`,
  },

  {
    name: 'Augmented Assignment',
    file: '(natural syntax)',
    syntax: ['x += expr', 'x -= expr', 'x *= expr', 'x /= expr'],
    description: 'Updates x using the given operator with expr. Each form expands to: x = @ x expr OP',
    example: `total = 0\ntotal += 5    # total = 5\ntotal *= 2    # total = 10\ntotal -= 3    # total = 7`,
  },

  {
    name: 'Not',
    file: '(natural syntax)',
    syntax: 'not expr :',
    description: 'Negates expr for use as an if/while condition. Stops token collection at : so the colon is not consumed. Expands to: expr !',
    example: `flag = 0\nif not @ flag :\n  print 1\nendif`,
  },

  {
    name: 'Pipeline',
    file: 'pipeline.kw',
    syntax: '*val |> *func',
    description: 'Rewrites to: func val. Lets the value appear on the left of a function for readability. Composes naturally with print, max, and any user-defined keyword.',
    example: `@ x |> print            # same as: print @ x\n@ a @ b A |> print      # same as: print @ a @ b A`,
  },

  {
    name: 'Max',
    file: 'max.kw',
    syntax: 'max ?a ?b',
    description: 'Compares the values of variables a and b. Stores the larger in _max. Expands to an if/else that assigns _max. Use @ _max to read the result.',
    example: `a = 3\nb = 7\nmax a b\nprint @ _max   # 7`,
  },

  { section: 'Caching' },

  {
    name: 'Memoize',
    file: 'memoize.kw',
    syntax: 'memoize ?result = *expr using ?cache',
    description: 'On first call (cache == 0): evaluates expr, stores in result, saves result + 999999 in cache. On subsequent calls: recovers result from cache without re-evaluating expr.',
    note: 'Cache stores result + 999999 to distinguish "nothing cached" (0) from a legitimate zero result.',
    example: `cache = 0\nmemoize result = 6 7 M using cache   # computes 42\nmemoize result = 100 100 M using cache   # returns 42\nprint @ result   # 42`,
  },

  { section: 'Type System' },

  {
    name: 'Type Declaration',
    file: 'typedef.kw',
    syntax: ['typedef int ?name', 'typedef pos ?name', 'typedef neg ?name'],
    description: 'Stores a compile-time type tag for name in ct_state. int = any value, no runtime guard. pos = must be > 0. neg = must be < 0. Emits zero opcodes.',
    example: `typedef pos x   # x must always be > 0\ntypedef neg y   # y must always be < 0\ntypedef int z   # z unconstrained`,
  },

  {
    name: 'Typed Assignment',
    file: 'tassign.kw',
    syntax: 'tassign ?name = *expr',
    description: 'Assigns expr to name, then emits an inline runtime guard based on the declared type. If the value violates the constraint, the program halts at that point with no output.',
    example: `typedef pos x\ntassign x = 5     # ok\ntassign x = -3    # halts at runtime`,
  },

  {
    name: 'Type Inference',
    file: 'tinfer.kw',
    syntax: [
      'tinfer ?result = *expr typed ?a plus ?b',
      'tinfer ?result = *expr typed ?a times ?b',
    ],
    description: 'Infers result type from the declared types of a and b at compile time, then assigns and guards. Rules: pos+pos→pos, neg+neg→neg, mixed→int, pos×pos→pos, neg×neg→pos, any×0→int.',
    example: `typedef pos a\ntassign a = 3\ntypedef pos b\ntassign b = 4\ntinfer c = @ a @ b A typed a plus b   # c inferred pos`,
  },

  { section: 'Ownership' },

  {
    name: 'Own',
    file: 'own.kw',
    syntax: 'own ?name',
    description: 'Marks name as owned in ct_state (state = 1). Pure compile-time — emits no opcodes. Required before move will permit a transfer from this variable.',
    example: `x = 99\nown x`,
  },

  {
    name: 'Move',
    file: 'move.kw',
    syntax: 'move ?from to ?to',
    description: 'Transfers ownership: checks from is owned (halts if not), sets from to moved (state 2) and to to owned (state 1). Compile-time only — does not copy the runtime value.',
    note: 'Assign the value manually before calling move. move only transfers the ownership tag, not the data.',
    example: `x = 99\nown x\ny = @ x      # copy value first\nmove x to y  # transfer ownership tag\nprint @ y    # 99`,
  },

  {
    name: 'Safe Buffer Use',
    file: 'buse.kw',
    syntax: 'buse ?name = *expr',
    description: 'Checks that name has not been moved (halts if state == 2), then assigns. Prevents writing to a variable whose ownership has already been transferred out.',
    note: 'Guards post-move use only. Does not prevent double-assign on an unowned variable.',
    example: `x = 5\nown x\ny = @ x\nmove x to y\nbuse x = 10   # halts: x was moved`,
  },

  {
    name: 'Ownership Check',
    file: 'bcheck.kw',
    syntax: '_bcheck ?name',
    description: 'Emits a runtime halt if name is in moved state (state == 2). Used internally by buse. Call directly when you need a custom ownership guard at an arbitrary point.',
    example: `_bcheck x   # halts at runtime if x was moved`,
  },

];

// ─────────────────────────────────────────────────────────────────
// BUILD DOCUMENT CONTENT
// ─────────────────────────────────────────────────────────────────

const content = [];

// ── COVER ────────────────────────────────────────────────────────
content.push(sp(2000, 0));

content.push(new Paragraph({
  spacing: { before: 0, after: 80 },
  children: [new TextRun({
    text: 'ELI',
    font: F.ui,
    size: pt(52),
    bold: true,
    color: C.deep,
  })],
}));

content.push(new Paragraph({
  spacing: { before: 0, after: 320 },
  children: [new TextRun({
    text: 'Feature Reference',
    font: F.prose,
    size: pt(20),
    color: C.mid,
    italics: true,
  })],
}));

content.push(new Paragraph({
  spacing: { before: 0, after: 0 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: C.deep, space: 1 } },
  children: [],
}));

content.push(sp(120, 0));

content.push(new Paragraph({
  spacing: { before: 0, after: 0 },
  children: [new TextRun({
    text: 'One entry per .kw file or natural syntax rule. Add to the features array when you add a feature.',
    font: F.prose,
    size: pt(9.5),
    color: C.muted,
    italics: true,
  })],
}));

content.push(new Paragraph({ children: [new PageBreak()] }));

// ── TABLE OF CONTENTS ────────────────────────────────────────────
content.push(new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 0, after: 160 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.deep, space: 6 } },
  children: [new TextRun({
    text: 'Contents',
    font: F.ui,
    size: pt(13),
    bold: true,
    color: C.deep,
  })],
}));

content.push(new TableOfContents('Contents', {
  hyperlink: true,
  headingStyleRange: '1-1',
}));

content.push(new Paragraph({ children: [new PageBreak()] }));

// ── FEATURES ─────────────────────────────────────────────────────
let firstInSection = true;

features.forEach((f, idx) => {
  if (f.section) {
    content.push(sectionHeading(f.section));
    content.push(sp(160, 0));
    firstInSection = true;
  } else {
    if (!firstInSection) {
      // Thin rule between entries within same section
      content.push(new Paragraph({
        spacing: { before: 0, after: 0 },
        border: { bottom: thinRule() },
        children: [],
      }));
      content.push(sp(60, 0));
    }
    content.push(featureEntry(f));
    firstInSection = false;
  }
});

// ── INDEX ────────────────────────────────────────────────────────
content.push(new Paragraph({ children: [new PageBreak()] }));

content.push(sectionHeading('Index'));
content.push(sp(120, 0));

content.push(new Paragraph({
  spacing: { before: 0, after: 120 },
  children: [new TextRun({
    text: 'All features at a glance. Feature name, syntax signature, source file, and section.',
    font: F.prose,
    size: pt(10),
    color: C.mid,
    italics: true,
  })],
}));

content.push(buildIndex(features));
content.push(sp(200, 0));

// ─────────────────────────────────────────────────────────────────
// DOCUMENT
// ─────────────────────────────────────────────────────────────────

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: F.prose, size: pt(10.5), color: C.ink } },
    },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: pt(13), bold: true, font: F.ui, color: C.deep },
        paragraph: { spacing: { before: 640, after: 0 }, outlineLevel: 0 },
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          spacing: { before: 0, after: 0 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.rule, space: 4 } },
          tabStops: [{ type: TabStopType.RIGHT, position: TOTAL_W }],
          children: [
            new TextRun({ text: 'ELI  —  Feature Reference', font: F.ui, size: pt(8.5), color: C.muted }),
          ],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          spacing: { before: 0, after: 0 },
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: C.rule, space: 4 } },
          tabStops: [{ type: TabStopType.RIGHT, position: TOTAL_W }],
          children: [
            new TextRun({ text: '\t', font: F.ui, size: pt(8.5) }),
            new TextRun({ children: [PageNumber.CURRENT], font: F.ui, size: pt(8.5), color: C.muted }),
          ],
        })],
      }),
    },
    children: content,
  }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync('/home/claude/ELI_Features.docx', b);
  console.log('Done');
});
