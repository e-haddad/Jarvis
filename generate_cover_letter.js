const { Document, Packer, Paragraph, TextRun, AlignmentType } = require('docx');
const fs = require('fs');
const path = require('path');

// Content passed as JSON via stdin
let raw = '';
process.stdin.on('data', d => raw += d);
process.stdin.on('end', async () => {
    const data = JSON.parse(raw);
    const { content, output_path } = data;

    // Parse the letter content into sections
    // Expected format: lines of text, blank lines = paragraph breaks
    const lines = content.split('\n');
    const paragraphs = [];

    for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed === '') {
            // Empty line = paragraph spacer
            paragraphs.push(new Paragraph({
                children: [new TextRun('')],
                spacing: { after: 0 }
            }));
        } else {
            paragraphs.push(new Paragraph({
                children: [new TextRun({
                    text: trimmed,
                    font: 'Arial',
                    size: 24, // 12pt
                })],
                spacing: { after: 0, line: 276 }, // 1.15 line spacing
                alignment: AlignmentType.LEFT,
            }));
        }
    }

    const doc = new Document({
        styles: {
            default: {
                document: {
                    run: { font: 'Arial', size: 24 }
                }
            }
        },
        sections: [{
            properties: {
                page: {
                    size: { width: 12240, height: 15840 }, // US Letter
                    margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } // 1 inch margins
                }
            },
            children: paragraphs
        }]
    });

    const buffer = await Packer.toBuffer(doc);

    // Ensure output directory exists
    const dir = path.dirname(output_path);
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }

    fs.writeFileSync(output_path, buffer);
    console.log('SAVED:' + output_path);
});
