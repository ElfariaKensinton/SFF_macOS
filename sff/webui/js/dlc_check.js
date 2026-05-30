// SteaMidra - Steam game setup and manifest tool (SFF)
// Copyright (c) 2025-2026 Midrag (https://github.com/Midrags)
//
// This file is part of SteaMidra.
//
// SteaMidra is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// SteaMidra is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with SteaMidra.  If not, see <https://www.gnu.org/licenses/>.

// DLC check modal — renders the structured payload emitted by
// `WebBridge.dlc_check_get_list`. Replaces the old run_game_action
// path that piped Rich console tables into a stdout the Web UI
// never displayed.
(function () {
    'use strict';

    var _initialized = false;
    var _currentAppId = '';

    function _escape(s) {
        var d = document.createElement('div');
        d.textContent = s == null ? '' : String(s);
        return d.innerHTML;
    }

    function _setLoading(text) {
        var body = document.getElementById('dlc-check-body');
        if (!body) return;
        body.innerHTML =
            '<div class="dlc-check-loading">' +
            '<svg class="spinner" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
            '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="42 16" stroke-linecap="round"></circle></svg>' +
            '<span>' + _escape(text) + '</span>' +
            '</div>';
    }

    function _renderEmpty(message) {
        var body = document.getElementById('dlc-check-body');
        if (!body) return;
        body.innerHTML = '<p class="dlc-check-empty">' + _escape(message) + '</p>';
    }

    function _renderError(message) {
        var body = document.getElementById('dlc-check-body');
        if (!body) return;
        body.innerHTML =
            '<p class="dlc-check-error">' + _escape(message) + '</p>';
    }

    function _renderList(payload) {
        var body = document.getElementById('dlc-check-body');
        var summary = document.getElementById('dlc-check-summary');
        if (!body) return;

        var dlcs = payload.dlcs || [];
        if (!dlcs.length) {
            _renderEmpty('No DLCs found for this game.');
            if (summary) summary.textContent = '';
            return;
        }

        if (summary) {
            var owned = payload.owned_count || 0;
            var total = payload.total_count || dlcs.length;
            summary.textContent = owned + ' of ' + total + ' unlocked';
        }

        var rows = dlcs.map(function (dlc) {
            var status = dlc.in_applist
                ? '<span class="dlc-status dlc-status-ok">Unlocked</span>'
                : '<span class="dlc-status dlc-status-missing">Missing</span>';
            var keyTag = '';
            if (dlc.type === 'depot') {
                keyTag = dlc.has_key
                    ? ' <span class="dlc-tag dlc-tag-ok" title="Decryption key present in config.vdf">key</span>'
                    : ' <span class="dlc-tag dlc-tag-warn" title="Decryption key missing — depot won\'t decrypt">no key</span>';
            }
            var typeTag = dlc.type === 'depot'
                ? '<span class="dlc-tag">depot</span>'
                : '<span class="dlc-tag">app id</span>';
            // Per-row Download button. Only shows for missing app-id-type
            // DLCs (depots can't be downloaded as standalone games), and
            // it queues the same fastest-download flow the Store tab uses,
            // just for the DLC's appid. Hubcap by default; users can pick
            // a different provider via the bulk buttons in the footer.
            var dlBtn = '';
            if (!dlc.in_applist && dlc.type !== 'depot') {
                dlBtn = '<button class="btn dlc-row-dl" data-appid="' + _escape(dlc.id) + '" data-name="' + _escape(dlc.name) + '" style="padding:2px 10px;font-size:12px;">Download</button>';
            } else {
                dlBtn = '';
            }
            return (
                '<tr>' +
                '<td>' + status + '</td>' +
                '<td class="dlc-id">' + _escape(dlc.id) + '</td>' +
                '<td>' + _escape(dlc.name) + '</td>' +
                '<td>' + typeTag + keyTag + '</td>' +
                '<td>' + dlBtn + '</td>' +
                '</tr>'
            );
        }).join('');

        body.innerHTML =
            '<table class="dlc-check-table">' +
            '<thead><tr>' +
            '<th>Status</th><th>App ID</th><th>Name</th><th>Type</th><th></th>' +
            '</tr></thead>' +
            '<tbody>' + rows + '</tbody>' +
            '</table>';

        // Wire per-row download buttons. Per-row default is now oureveryday
        // because Hubcap/Ryuu need the FULL game zip path (queues the
        // parent appid bundle), and a single per-row button can't ask the
        // user to confirm theyre OK redownloading the whole game just to
        // unlock a single DLC. The bulk picker exposes Hubcap/Ryuu/Oureveryday
        // explicitly so the user picks knowingly.
        body.querySelectorAll('.dlc-row-dl').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var appid = this.dataset.appid;
                var name = this.dataset.name || ('App ' + appid);
                if (!appid) return;
                if (!_currentAppId) {
                    Components.showToast('warning', 'Parent app id missing.');
                    return;
                }
                Components.showToast('info', 'Queued DLC ' + name + ' (oureveryday)...');
                Bridge.call('download_dlc_oureveryday', String(appid), String(_currentAppId));
            });
        });

        // Bulk-download buttons. Provider routing:
        //   * hubcap / ryuu   -> queue the PARENT game's appid via the
        //                        normal store flow. Hubcap/Ryuu only know
        //                        how to ship the full game zip, so we
        //                        download the parent which already covers
        //                        every DLC in one shot. Single call, not
        //                        one per DLC.
        //   * oureveryday     -> per-DLC manifest+key pull that appends to
        //                        the parent's existing lua without nuking
        //                        any keys the user already has. Loops over
        //                        each missing DLC.
        var bulk = document.getElementById('dlc-check-bulk-actions');
        var missing = dlcs.filter(function (d) {
            return !d.in_applist && d.type !== 'depot';
        });
        if (bulk) {
            bulk.style.display = missing.length ? 'flex' : 'none';
            bulk.querySelectorAll('.dlc-bulk-dl').forEach(function (btn) {
                btn.onclick = function () {
                    var src = this.dataset.source || 'oureveryday';
                    if (!_currentAppId) {
                        Components.showToast('warning', 'Parent app id missing.');
                        return;
                    }
                    if (src === 'hubcap' || src === 'ryuu') {
                        Components.showToast('info',
                            'Queueing parent app (' + _currentAppId + ') through ' + src +
                            ' — DLCs will come with it.');
                        Bridge.call('download_game_with_source',
                            String(_currentAppId), src, '0');
                        return;
                    }
                    // oureveryday: per-DLC append
                    Components.showToast('info', 'Queueing ' + missing.length + ' DLC(s) through oureveryday...');
                    missing.forEach(function (d) {
                        Bridge.call('download_dlc_oureveryday',
                            String(d.id), String(_currentAppId));
                    });
                };
            });
        }
    }

    function show(appId) {
        if (!appId) {
            Components.showToast('warning', 'Please select a game first.');
            return;
        }
        _currentAppId = String(appId);
        var titleEl = document.getElementById('dlc-check-title');
        var summaryEl = document.getElementById('dlc-check-summary');
        if (titleEl) titleEl.textContent = 'DLC Check — App ' + _currentAppId;
        if (summaryEl) summaryEl.textContent = '';
        Components.showModal('dlc-check-modal');
        _setLoading('Fetching DLC list from Steam...');
        Bridge.call('dlc_check_get_list', _currentAppId);
    }

    function _onTaskFinished(json) {
        try {
            var data = JSON.parse(json);
            if (data.task !== 'dlc_check') return;
            if (data.app_id && data.app_id !== _currentAppId) return;
            if (!data.success) {
                _renderError(data.message || 'Failed to fetch DLC list.');
                return;
            }
            var titleEl = document.getElementById('dlc-check-title');
            if (titleEl && data.base_name) {
                titleEl.textContent = 'DLC Check — ' + data.base_name;
            }
            _renderList(data);
        } catch (e) {
            _renderError('Could not parse DLC payload.');
        }
    }

    function init() {
        if (_initialized) return;
        _initialized = true;
        Bridge.on('task_finished', _onTaskFinished);
    }

    window.DlcCheck = { init: init, show: show };
})();
