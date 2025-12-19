import { useEffect } from "react";

/**
 * 通用模态框组件
 * @param {boolean} isOpen - 是否显示
 * @param {function} onClose - 关闭回调
 * @param {string} title - 标题
 * @param {string} type - 类型：warning, info, success, error
 * @param {React.ReactNode} children - 内容
 */
function Modal({ isOpen, onClose, title, type = "warning", children }) {
  // 按ESC键关闭
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      document.addEventListener("keydown", handleEsc);
    }
    return () => document.removeEventListener("keydown", handleEsc);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const iconMap = {
    warning: "⚠️",
    info: "ℹ️",
    success: "✅",
    error: "❌",
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-container"
        onClick={(e) => e.stopPropagation()}
        data-type={type}
      >
        <div className="modal-header">
          <span className="modal-icon">{iconMap[type]}</span>
          <h3 className="modal-title">{title}</h3>
        </div>
        <div className="modal-body">{children}</div>
        <div className="modal-footer">
          <button className="btn btn-primary modal-btn" onClick={onClose}>
            我已知晓
          </button>
        </div>
      </div>
    </div>
  );
}

export default Modal;
