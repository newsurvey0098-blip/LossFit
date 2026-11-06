import {readdirSync, readFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
import {describe, expect, it} from 'vitest';

const sourceDirectory = path.dirname(fileURLToPath(import.meta.url));

function sourceFiles(directory) {
  return readdirSync(directory, {withFileTypes: true}).flatMap((entry) => {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(file);
    if (!entry.name.endsWith('.tsx') || /\.(test|spec)\.tsx$/.test(entry.name)) return [];
    return [file];
  });
}

function jsxAttributeValue(attribute) {
  if (!attribute.initializer) return '';
  if (ts.isStringLiteral(attribute.initializer)) return attribute.initializer.text;
  if (ts.isJsxExpression(attribute.initializer) && attribute.initializer.expression && ts.isStringLiteral(attribute.initializer.expression)) {
    return attribute.initializer.expression.text;
  }
  return null;
}

function lineAt(source, node) {
  return source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
}

describe('source-level interactive UI invariants', () => {
  it('declares button intent for click handlers inside forms', () => {
    const violations = [];

    for (const file of sourceFiles(sourceDirectory)) {
      const ast = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

      function visit(node, formDepth = 0) {
        const isForm = ts.isJsxElement(node) && node.openingElement.tagName.getText(ast) === 'form';
        if (ts.isJsxElement(node) && node.openingElement.tagName.getText(ast) === 'button' && formDepth > 0) {
          const attributes = node.openingElement.attributes.properties;
          const hasClickHandler = attributes.some((attribute) => ts.isJsxAttribute(attribute) && attribute.name.getText(ast) === 'onClick');
          const hasExplicitType = attributes.some((attribute) => ts.isJsxAttribute(attribute) && attribute.name.getText(ast) === 'type');
          if (hasClickHandler && !hasExplicitType) {
            violations.push(`${path.relative(sourceDirectory, file)}:${lineAt(ast, node)} has a clickable form button without an explicit type`);
          }
        }
        ts.forEachChild(node, (child) => visit(child, formDepth + (isForm ? 1 : 0)));
      }

      visit(ast);
    }

    expect(violations).toEqual([]);
  });

  it('does not ship hard-coded placeholder links', () => {
    const violations = [];

    for (const file of sourceFiles(sourceDirectory)) {
      const ast = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

      function visit(node) {
        if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
          const tag = node.tagName.getText(ast);
          if (tag === 'a' || tag === 'Link') {
            for (const attribute of node.attributes.properties) {
              if (!ts.isJsxAttribute(attribute) || !['href', 'to'].includes(attribute.name.getText(ast))) continue;
              const value = jsxAttributeValue(attribute);
              if (value !== null && (value.trim() === '' || value.trim() === '#' || /^javascript:/i.test(value.trim()))) {
                violations.push(`${path.relative(sourceDirectory, file)}:${lineAt(ast, node)} has a placeholder link`);
              }
            }
          }
        }
        ts.forEachChild(node, visit);
      }

      visit(ast);
    }

    expect(violations).toEqual([]);
  });
});
