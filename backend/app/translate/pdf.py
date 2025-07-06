import os
import logging
import shutil
import asyncio
import datetime
from pathlib import Path
from . import common, db, to_translate

from babeldoc.translator.translator import OpenAITranslator
from babeldoc.docvision.base_doclayout import DocLayoutModel
from babeldoc.format.pdf.translation_config import TranslationConfig, WatermarkOutputMode
from babeldoc.format.pdf.high_level import async_translate
from babeldoc.docvision.table_detection.rapidocr import RapidOCRModel
import babeldoc
import pytz
from flask import current_app



logger = logging.getLogger(__name__)


def clean_output_filename(original_path: Path, output_dir: str, config: TranslationConfig) -> Path:
    """清理babeldoc生成的多余后缀"""
    stem = original_path.stem.split('.')[0]
    new_path = Path(output_dir) / f"{stem}{original_path.suffix}"
    logger.info(f"clean_output_filename: {new_path}")
    # 支持所有可能的输出文件名变体
    for suffix in [
        f'.no_watermark.{config.lang_out}.{'mono' if config.no_dual else 'dual' }',
    ]:
        temp_path = Path(output_dir) / f"{stem}{suffix}{original_path.suffix}"
        logger.info(f"temp_path: {temp_path}")
        if temp_path.exists():
            shutil.move(temp_path, new_path)
            break

    return new_path if new_path.exists() else None


async def async_translate_pdf(trans):
    """异步PDF翻译核心函数"""
    try:
        start_time = datetime.datetime.now(pytz.timezone(current_app._get_current_object().config['TIMEZONE']))
        original_path = Path(trans['file_path'])

        # 初始化翻译库
        babeldoc.format.pdf.high_level.init() 
        
        # 转换语言代码
        target_lang = common.convert_language_name_to_code(trans['lang'])

        # 初始化文档布局模型
        doc_layout_model = DocLayoutModel.load_onnx()

        # 初始化表格模型（根据参数决定是否启用）
        table_model = RapidOCRModel() if trans.get('translate_table', False) else None

        # 创建翻译器实例
        translator = OpenAITranslator(
            lang_in="auto",
            lang_out=target_lang,
            model=trans.get('model', 'gpt-4'),
            api_key=trans['api_key'],
            base_url=trans.get('api_url', 'https://api.openai.com/v1'),
            ignore_cache=False
        )

        # 完整翻译配置
        # cons=PConfig()
        config = TranslationConfig(
            input_file=str(original_path),
            output_dir=str(trans['target_path_dir']),
            translator=translator,
            lang_in="auto",
            lang_out=target_lang,
            doc_layout_model=doc_layout_model,
            watermark_output_mode=WatermarkOutputMode.NoWatermark,
            min_text_length=3,
            pages=None,
            qps=16,
            #translate_table_text=True,
            table_model=table_model,  # 传递表格模型
            translate_table_text=True,  # 表格翻译开关
            show_char_box=True, # 调试表格识别
            no_dual=True,  # 是否生成双语PDF
            no_mono=False,  # 是否生成单语PDF
            skip_scanned_detection=True,
        )

        # 执行翻译
        async for event in async_translate(config):
            if event["type"] == "progress":
                db.execute(
                    "UPDATE translate SET process=%s WHERE id=%s",
                    int(event["progress"] * 100),
                    trans['id']
                )
            elif event["type"] == "finish":
                # 处理输出文件名
                final_path = clean_output_filename(original_path, trans['target_path_dir'], config)
                print(f"translate_resulte : {event['translate_result']}")
                # 更新数据库记录
                if final_path:
                    db.execute(
                        "UPDATE translate SET target_filepath=%s WHERE id=%s",
                        str(final_path),
                        trans['id']
                    )

                # 计算token使用量
                token_count = getattr(translator, 'token_count', 0)
                prompt_tokens = getattr(translator, 'prompt_token_count', 0)
                completion_tokens = getattr(translator, 'completion_token_count', 0)
                logger.info(f"token_count: {token_count}, prompt_tokens: {prompt_tokens}, completion_tokens: {completion_tokens}")

                # 触发完成回调
                end_time = datetime.datetime.now(pytz.timezone(current_app._get_current_object().config['TIMEZONE']))
                spend_time=common.display_spend(start_time, end_time)

                to_translate.complete(
                    trans,
                    text_count=1,  # PDF按文件计数
                    spend_time=spend_time
                )
                return True

    except Exception as e:
        logger.error(f"PDF翻译失败: {str(e)}", exc_info=True)
        db.execute(
            "UPDATE translate SET status='failed', failed_reason=%s WHERE id=%s",
            str(e), trans['id']
        )
        return False


def translate_pdf(trans):
    """同步入口"""
    return asyncio.run(async_translate_pdf(trans))


def start(trans):
    """启动PDF翻译（与TXT翻译保持相同接口）"""
    try:
        # 参数检查
        original_path = Path(trans['file_path'])
        if not original_path.exists():
            raise FileNotFoundError(f"文件不存在: {trans['file_path']}")

        start_time = datetime.datetime.now(pytz.timezone(current_app._get_current_object().config['TIMEZONE']))
        # 初始化任务状态
        db.execute(
            "UPDATE translate SET status='process', process=0, start_at=%s WHERE id=%s",
            start_time,
            trans['id']
        )

        # 确保输出目录存在
        os.makedirs(trans['target_path_dir'], exist_ok=True)

        # 执行翻译
        success = translate_pdf(trans)

        if not success:
            raise RuntimeError("PDF翻译过程失败")

        return True

    except Exception as e:
        logger.error(f"PDF任务初始化失败: {str(e)}")
        db.execute(
            "UPDATE translate SET status='failed', failed_reason=%s WHERE id=%s",
            str(e), trans['id']
        )
        return False
