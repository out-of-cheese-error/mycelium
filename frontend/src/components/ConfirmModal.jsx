import { useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import './ConfirmModal.css';

/**
 * Custom confirmation modal that works in both browser and Tauri
 */
function ConfirmModalUI({ message, onConfirm, onCancel }) {
    return (
        <div className="confirm-modal-overlay" onClick={onCancel}>
            <div className="confirm-modal" onClick={e => e.stopPropagation()}>
                <p className="confirm-modal-message">{message}</p>
                <div className="confirm-modal-buttons">
                    <button className="confirm-modal-cancel" onClick={onCancel}>
                        Cancel
                    </button>
                    <button className="confirm-modal-confirm" onClick={onConfirm}>
                        Confirm
                    </button>
                </div>
            </div>
        </div>
    );
}

/**
 * Show a confirmation dialog that works in Tauri
 * @param {string} message - The message to display
 * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
 */
export function confirm(message) {
    return new Promise((resolve) => {
        const container = document.createElement('div');
        container.id = 'confirm-modal-container';
        document.body.appendChild(container);

        const root = createRoot(container);

        const cleanup = () => {
            root.unmount();
            container.remove();
        };

        const handleConfirm = () => {
            cleanup();
            resolve(true);
        };

        const handleCancel = () => {
            cleanup();
            resolve(false);
        };

        root.render(
            <ConfirmModalUI
                message={message}
                onConfirm={handleConfirm}
                onCancel={handleCancel}
            />
        );
    });
}

export default { confirm };
