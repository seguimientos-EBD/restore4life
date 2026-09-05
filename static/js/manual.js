/* Places the numbered marks of the manual's figures.
 *
 * The marks are stored as percentages in `generic/manual.py`, which is the right place
 * for them and a miserable place to guess them from. Open any manual page with
 * `?markers=1`, click where a mark belongs, and this writes out the line to paste --
 * and puts it on the clipboard, since it exists to be pasted somewhere else.
 *
 * Off by default: without the parameter this file does nothing at all, so the manual
 * behaves like the ordinary page it is.
 */

(function() {
    'use strict';

    if (new URLSearchParams(window.location.search).get('markers') !== '1') {
        return;
    }

    function probe() {
        let element = document.querySelector('.manual-probe');
        if (!element) {
            element = document.createElement('div');
            element.className = 'manual-probe';
            document.body.appendChild(element);
        }
        return element;
    }

    function report(figure, x, y) {
        const line = 'Mark(' + x.toFixed(1) + ', ' + y.toFixed(1) + ", '')";
        const target = probe();
        target.textContent = figure + ' → ' + line;

        /* Clipboard access needs a secure context, which the dev server over plain HTTP
         * is not. The text is on screen either way, so a refusal is worth noting rather
         * than handling. */
        if (navigator.clipboard) {
            navigator.clipboard.writeText(line).then(function() {
                target.textContent += '  (copied)';
            }, function() {
                target.textContent += '  (select and copy by hand)';
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        document.body.classList.add('manual-placing');

        document.querySelectorAll('.manual-shot[data-figure]').forEach(function(shot) {
            shot.addEventListener('click', function(event) {
                const box = shot.getBoundingClientRect();
                report(
                    shot.dataset.figure,
                    ((event.clientX - box.left) / box.width) * 100,
                    ((event.clientY - box.top) / box.height) * 100
                );
            });
        });

        probe().textContent = 'Mark placement on: click a screenshot to read its position.';
    });
}());
