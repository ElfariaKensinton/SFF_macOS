/**
 * SteaMidra — A12 Bulk Import (Folder Scan + Drag-and-Drop)
 *
 * Wires three surfaces (Folder Scan button, dedicated Drop Zone, Quick
 * Start drop) into the singleton BulkImportQueue exposed by web_bridge.py.
 * Validation is browser-side first (.lua / .manifest extension; SHA-256
 * dedupe via SubtleCrypto when available, path-only fallback otherwise),
 * the bridge re-validates with the existing single-file parsers.
 *
 * Files of any other extension are recorded as skipped with reason
 * "unsupported file type" and are NOT passed to enqueue.
 */

(function () {
    'use strict';

    // Skip-reason strings — must match the BulkImportQueue constants in
    // sff/gui/bulk_import.py and the i18n keys in webui_*.json.
    var SKIP_UNSUPPORTED = 'unsupported file type';
    var SKIP_DUPLICATE_PREFIX = 'duplicate of ';

    // Per-batch dedupe state. Cleared whenever the user kicks off a new
    // batch (e.g. clicks Select Folder again or drops a fresh set).
    var seenPaths = new Set();
    var seenHashes = new Set();
    var localSkipped = []; // [{path, reason}]
    var aggregateTotal = 0;
    var aggregateProcessed = 0;
    var resultsByPath = Object.create(null);

    function _$(id) { return document.getElementById(id); }

    function _show(el) { if (el) el.classList.remove('hidden'); }
    function _hide(el) { if (el) el.classList.add('hidden'); }

    function _ext(name) {
        var i = name.lastIndexOf('.');
        return i < 0 ? '' : name.slice(i).toLowerCase();
    }

    function _isImportable(name) {
        var e = _ext(name);
        return e === '.lua' || e === '.zip' || e === '.manifest';
    }

    function _hashFile(file) {
        // SHA-256 dedupe via SubtleCrypto; fall back to path-only when
        // the API is unavailable (older webviews).
        if (!file || !window.crypto || !window.crypto.subtle) {
            return Promise.resolve(null);
        }
        return file.arrayBuffer().then(function (buf) {
            return window.crypto.subtle.digest('SHA-256', buf);
        }).then(function (digest) {
            var bytes = new Uint8Array(digest);
            var hex = '';
            for (var i = 0; i < bytes.length; i++) {
                hex += bytes[i].toString(16).padStart(2, '0');
            }
            return hex;
        }).catch(function () { return null; });
    }

    function _path(file) {
        // Drag-and-drop in QtWebEngine usually exposes file.path; falls
        // back to file.name when running in plain browsers.
        return file.path || file.webkitRelativePath || file.name || '';
    }

    function _resetUI() {
        var bar = _$('aggregate-progress');
        var fill = _$('aggregate-progress-fill');
        var label = _$('aggregate-progress-label');
        var panel = _$('results-panel');
        var list = _$('bulk-results-list');
        if (bar) _hide(bar);
        if (fill) fill.style.width = '0%';
        if (label) label.textContent = '0 / 0';
        if (panel) _hide(panel);
        if (list) list.innerHTML = '';
        seenPaths = new Set();
        seenHashes = new Set();
        localSkipped = [];
        aggregateTotal = 0;
        aggregateProcessed = 0;
        resultsByPath = Object.create(null);
    }

    function _showAggregate() {
        var bar = _$('aggregate-progress');
        if (bar) _show(bar);
    }

    function _renderAggregate(processed, total) {
        if (typeof processed === 'number') aggregateProcessed = processed;
        if (typeof total === 'number' && total > 0) aggregateTotal = total;
        var label = _$('aggregate-progress-label');
        var fill = _$('aggregate-progress-fill');
        if (label) {
            label.textContent = aggregateProcessed + ' / ' + aggregateTotal;
        }
        if (fill) {
            var pct = aggregateTotal > 0
                ? Math.round((aggregateProcessed / aggregateTotal) * 100)
                : 0;
            fill.style.width = pct + '%';
        }
    }

    function _renderSkipped(records) {
        if (!records || !records.length) return;
        var panel = _$('results-panel');
        var list = _$('bulk-results-list');
        if (!panel || !list) return;
        _show(panel);
        records.forEach(function (rec) {
            var li = document.createElement('li');
            li.className = 'bulk-result-item bulk-result-skipped';
            li.textContent = (rec.path || '') + ' — ' + (rec.reason || '');
            list.appendChild(li);
        });
    }

    function _renderResult(rec) {
        var panel = _$('results-panel');
        var list = _$('bulk-results-list');
        if (!panel || !list) return;
        _show(panel);
        var li = document.createElement('li');
        var cls = rec.skipped ? 'bulk-result-skipped'
            : (rec.ok ? 'bulk-result-ok' : 'bulk-result-fail');
        li.className = 'bulk-result-item ' + cls;
        var msg = (rec.path || '');
        if (rec.app_id) msg += ' [App ' + rec.app_id + ']';
        if (rec.reason) msg += ' — ' + rec.reason;
        if (rec.failing_step) msg += ' (' + rec.failing_step + ')';
        li.textContent = msg;
        list.appendChild(li);
    }

    function _onProgress(payload) {
        if (!payload || payload.task !== 'bulk_import') return;
        if (typeof payload.processed === 'number' && typeof payload.total === 'number') {
            _renderAggregate(payload.processed, payload.total);
        }
        // Per-file finalization
        if (payload.status === 'done' && payload.file) {
            var rec = {
                path: payload.file,
                app_id: payload.app_id || '',
                ok: payload.ok !== false,
                reason: payload.reason || '',
                failing_step: payload.failing_step || '',
            };
            resultsByPath[payload.file] = rec;
            _renderResult(rec);
        }
    }

    function _onTaskFinished(payload) {
        if (!payload || payload.task !== 'bulk_import') return;
        // Use the bridge-side summary as the source of truth for the
        // final render; replace any partial UI rows the per-file
        // progress events might have produced.
        var list = _$('bulk-results-list');
        if (list) list.innerHTML = '';
        (payload.results || []).forEach(_renderResult);
        _renderAggregate(payload.total || 0, payload.total || 0);
        if (window.Components && Components.showToast) {
            var msg = 'Bulk import: ' + (payload.succeeded || 0) + ' ok, '
                + (payload.failed || 0) + ' failed, '
                + (payload.skipped || 0) + ' skipped';
            Components.showToast(payload.success ? 'success' : 'warning', msg);
        }
    }

    function _classifyDrop(files) {
        // Split a FileList/array into (importable, skipped[]).
        var importable = [];
        var skipped = [];
        for (var i = 0; i < files.length; i++) {
            var f = files[i];
            var name = f.name || '';
            if (_isImportable(name)) {
                importable.push(f);
            } else {
                skipped.push({ path: _path(f) || name, reason: SKIP_UNSUPPORTED });
            }
        }
        return { importable: importable, skipped: skipped };
    }

    function _dedupeAndCollectPaths(files) {
        // Returns a Promise<{paths: string[], skipped: [...]}>. Dedupe by
        // path first, content hash second. Mutates seenPaths/seenHashes.
        var skipped = [];
        var promises = [];
        files.forEach(function (file) {
            var path = _path(file);
            if (path && seenPaths.has(path)) {
                skipped.push({ path: path, reason: SKIP_DUPLICATE_PREFIX + path });
                return;
            }
            promises.push(_hashFile(file).then(function (hash) {
                if (hash && seenHashes.has(hash)) {
                    skipped.push({ path: path, reason: SKIP_DUPLICATE_PREFIX + hash.slice(0, 12) });
                    return null;
                }
                if (path) seenPaths.add(path);
                if (hash) seenHashes.add(hash);
                return path;
            }));
        });
        return Promise.all(promises).then(function (results) {
            var paths = results.filter(function (p) { return !!p; });
            return { paths: paths, skipped: skipped };
        });
    }

    function _enqueueDrop(files) {
        var classified = _classifyDrop(files);
        // Render skipped non-import drops immediately; they never reach
        // the bridge.
        if (classified.skipped.length) {
            _renderSkipped(classified.skipped);
            localSkipped = localSkipped.concat(classified.skipped);
        }
        if (!classified.importable.length) {
            return;
        }
        _showAggregate();
        _dedupeAndCollectPaths(classified.importable).then(function (out) {
            if (out.skipped.length) {
                _renderSkipped(out.skipped);
                localSkipped = localSkipped.concat(out.skipped);
            }
            if (!out.paths.length) return;
            // Update the local total estimate so the bar starts moving
            // before the bridge sends its first progress event.
            aggregateTotal += out.paths.length;
            _renderAggregate(aggregateProcessed, aggregateTotal);
            if (window.Bridge && Bridge.call) {
                Bridge.call('enqueue_dropped_files', JSON.stringify(out.paths));
            }
        });
    }

    function _wireDropTarget(el) {
        if (!el) return;
        var enter = function (e) {
            e.preventDefault();
            e.stopPropagation();
            el.classList.add('bulk-drop-active');
        };
        var leave = function (e) {
            e.preventDefault();
            e.stopPropagation();
            el.classList.remove('bulk-drop-active');
        };
        el.addEventListener('dragenter', enter);
        el.addEventListener('dragover', enter);
        el.addEventListener('dragleave', leave);
        el.addEventListener('drop', function (e) {
            e.preventDefault();
            e.stopPropagation();
            el.classList.remove('bulk-drop-active');
            var dt = e.dataTransfer;
            if (!dt || !dt.files || !dt.files.length) return;
            _enqueueDrop(dt.files);
        });
    }

    function _wireFolderScan() {
        var card = _$('bulk-import-folder');
        if (!card) return;
        card.addEventListener('click', function (e) {
            e.preventDefault();
            _resetUI();
            _showAggregate();
            if (window.Bridge && Bridge.call) {
                Bridge.call('open_folder_scan');
            }
        });
    }

    function _wireCancel() {
        var btn = _$('bulk-import-cancel');
        if (!btn) return;
        btn.addEventListener('click', function () {
            if (window.Bridge && Bridge.call) {
                Bridge.call('cancel_bulk_import');
            }
        });
    }

    function _showDropZoneOnDragHover() {
        // Show the drop zone the first time the user drags anything
        // onto the window so it stops feeling hidden but does not
        // pollute the layout when no drop is in progress.
        var dz = _$('drop-zone');
        if (!dz) return;
        var revealed = false;
        var reveal = function (e) {
            if (revealed) return;
            if (e && e.dataTransfer && Array.from(e.dataTransfer.types || []).indexOf('Files') < 0) {
                return;
            }
            _show(dz);
            revealed = true;
        };
        window.addEventListener('dragenter', reveal, true);
        window.addEventListener('dragover', reveal, true);
    }

    function init() {
        _wireFolderScan();
        _wireCancel();
        _wireDropTarget(_$('drop-zone'));
        // Quick Start area also accepts drops via the same enqueue path.
        var quickStart = document.querySelector('.section-group .section-title');
        // Wire the actual Quick Start container, not its title.
        var quickStartGroup = null;
        var titles = document.querySelectorAll('.section-group .section-title');
        for (var i = 0; i < titles.length; i++) {
            if ((titles[i].textContent || '').trim() === 'Quick Start') {
                quickStartGroup = titles[i].parentElement;
                break;
            }
        }
        _wireDropTarget(quickStartGroup);
        _showDropZoneOnDragHover();

        // Hook into existing bridge channels.
        if (window.Bridge) {
            if (Bridge.on) {
                Bridge.on('download_progress', function (json) {
                    try { _onProgress(JSON.parse(json)); } catch (e) {}
                });
                Bridge.on('task_finished', function (json) {
                    try { _onTaskFinished(JSON.parse(json)); } catch (e) {}
                });
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
