const fs = require('fs');
const path = '/Users/yanping.ma/PycharmProjects/Code-Platform/frontend/src/pages/WorkflowsPage.jsx';
const content = fs.readFileSync(path, 'utf8');
let parens = 0, braces = 0, brackets = 0;
for (const ch of content) {
  if (ch === '(') parens++;
  else if (ch === ')') parens--;
  else if (ch === '{') braces++;
  else if (ch === '}') braces--;
  else if (ch === '[') brackets++;
  else if (ch === ']') brackets--;
}
console.log(`Parentheses: ${parens}, Braces: ${braces}, Brackets: ${brackets}`);
if (parens !== 0 || braces !== 0 || brackets !== 0) {
  console.error('ERROR: Unbalanced brackets!');
} else {
  console.log('✓ Bracket balance OK');
}
