import re
text = """
#### Step 2: Create the Contact Route

**File: `backend/routes/contact.js`**
```javascript
const express = require('express');
const nodemailer = require('nodemailer');
```

And another one:
`frontend/src/App.js`
```
console.log('hello');
```
"""

lines = text.split('\n')
current_file = None
in_code_block = False
code_lines = []
for i, line in enumerate(lines):
    if line.startswith('```'):
        if not in_code_block:
            in_code_block = True
            code_lines = []
            current_file = None
            for j in range(i-1, max(-1, i-5), -1):
                m = re.search(r'(?:File|Path).*?[`\*]*([a-zA-Z0-9\_\-\.\/]+\.[a-zA-Z0-9]+)[`\*]*', lines[j], re.IGNORECASE)
                if m:
                    current_file = m.group(1)
                    break
            if not current_file:
                for j in range(i-1, max(-1, i-5), -1):
                    m = re.search(r'`([a-zA-Z0-9\_\-\.\/]+\.[a-zA-Z0-9]+)`', lines[j])
                    if m:
                        current_file = m.group(1)
                        break
            if not current_file:
                current_file = "generated.txt"
        else:
            in_code_block = False
            print(f"-> {current_file}")
            print("\n".join(code_lines))
    elif in_code_block:
        code_lines.append(line)
