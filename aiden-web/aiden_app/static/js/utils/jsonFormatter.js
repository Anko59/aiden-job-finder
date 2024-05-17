export function formatJson(obj, level = 0) {
    let indent = '  '.repeat(level);
    let formattedString = '';

    function wrapWithClass(value, cssClass) {
        return `<span class="${cssClass}">${value}</span>`;
    }

    if (Array.isArray(obj)) {
        formattedString += wrapWithClass('[', 'array');
        for (let i = 0; i < obj.length; i++) {
            formattedString += '\n' + indent + '  ' + formatJson(obj[i], level + 1);
            if (i < obj.length - 1) {
                formattedString += ',' + '\n' + indent + '  ';
            }
        }
        formattedString += wrapWithClass('\n' + indent + ']', 'array');
    } else if (typeof obj === 'object' && obj !== null) {
        formattedString += wrapWithClass('{', 'object');
        for (let key in obj) {
            formattedString += '\n' + indent + '  ' + wrapWithClass(`"${key}": `, 'key');
            formattedString += formatJson(obj[key], level + 1);
            if (Object.keys(obj).indexOf(key) < Object.keys(obj).length - 1) {
                formattedString += ',' + '\n' + indent + '  ';
            }
        }
        formattedString += wrapWithClass('\n' + indent + '}', 'object');
    } else if (typeof obj === 'string') {
        formattedString += wrapWithClass(`"${obj}"`, 'string');
    } else if (typeof obj === 'number') {
        formattedString += wrapWithClass(obj.toString(), 'number');
    } else if (typeof obj === 'boolean') {
        formattedString += wrapWithClass(obj.toString(), 'boolean');
    } else if (obj === null) {
        formattedString += wrapWithClass('null', 'null');
    }

    return formattedString;
}
