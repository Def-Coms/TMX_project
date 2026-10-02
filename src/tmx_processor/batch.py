"""Batch processing utilities for multiple TMX files."""
from __future__ import annotations

import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Iterator, List, Optional

from .parser import TMXParser, TranslationUnit
from .cleaner import CleanConfig, DataCleaner
from .deduper import DataDeduper
from .converter import DataConverter, OutputFormat, ConvertOptions


class BatchProcessor:
    """Process multiple TMX files in batch."""
    
    def __init__(
        self,
        clean: bool = True,
        dedupe: bool = True,
        fuzzy_dedupe: bool = False,
        clean_config: Optional[CleanConfig] = None,
    ):
        self.clean = clean
        self.dedupe = dedupe
        self.fuzzy_dedupe = fuzzy_dedupe
        self.clean_config = clean_config or CleanConfig()
        self.deduper = DataDeduper(exact=True, fuzzy=fuzzy_dedupe)
        self.converter = DataConverter()
    
    def process_file(
        self,
        tmx_path: Path,
        output_path: Path,
        fmt: OutputFormat = OutputFormat.JSONL,
        convert_options: Optional[ConvertOptions] = None,
    ) -> Dict[str, int]:
        """Process a single TMX file."""
        stats = {
            "input_units": 0,
            "after_clean": 0,
            "after_dedupe": 0,
            "output_units": 0,
        }
        
        # Parse
        parser = TMXParser(tmx_path)
        units = parser.parse_all()
        stats["input_units"] = len(units)
        
        # Clean
        if self.clean:
            cleaner = DataCleaner(self.clean_config)
            units = cleaner.clean_units(units)
        stats["after_clean"] = len(units)
        
        # Dedupe
        if self.dedupe:
            units = self.deduper.dedupe(list(units))
        stats["after_dedupe"] = len(units)
        
        # Convert
        opts = convert_options or ConvertOptions()
        converter = DataConverter(options=opts)
        converter.convert(units, output_path, fmt, instruction_tmpl=opts.instruction_template)
        stats["output_units"] = len(units)
        
        return stats
    
    def process_files(
        self,
        tmx_files: List[Path],
        output_dir: Path,
        fmt: OutputFormat = OutputFormat.JSONL,
        convert_options: Optional[ConvertOptions] = None,
        merge: bool = False,
    ) -> Dict[str, Dict[str, int]]:
        """Process multiple TMX files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        results = {}
        
        if merge:
            # Merge all files into one
            all_units = []
            for tmx_path in tmx_files:
                parser = TMXParser(tmx_path)
                units = parser.parse_all()
                all_units.extend(units)
            
            stats = {
                "input_units": len(all_units),
                "after_clean": len(all_units),
                "after_dedupe": len(all_units),
                "output_units": len(all_units),
            }
            
            if self.clean:
                cleaner = DataCleaner(self.clean_config)
                all_units = cleaner.clean_units(all_units)
                stats["after_clean"] = len(all_units)
            
            if self.dedupe:
                all_units = self.deduper.dedupe(list(all_units))
                stats["after_dedupe"] = len(all_units)
            
            output_path = output_dir / f"merged.{fmt.value}"
            opts = convert_options or ConvertOptions()
            converter = DataConverter(options=opts)
            converter.convert(all_units, output_path, fmt, instruction_tmpl=opts.instruction_template)
            stats["output_units"] = len(all_units)
            
            results["merged"] = stats
        else:
            # Process each file separately using ProcessPoolExecutor for multi-core parallelism
            if len(tmx_files) > 1:
                with ProcessPoolExecutor() as executor:
                    future_to_path = {}
                    for tmx_path in tmx_files:
                        output_name = tmx_path.stem + f".{fmt.value}"
                        output_path = output_dir / output_name
                        future = executor.submit(
                            self.process_file,
                            tmx_path,
                            output_path,
                            fmt,
                            convert_options,
                        )
                        future_to_path[future] = tmx_path
                    for future in as_completed(future_to_path):
                        tmx_path = future_to_path[future]
                        results[str(tmx_path)] = future.result()
            else:
                for tmx_path in tmx_files:
                    output_name = tmx_path.stem + f".{fmt.value}"
                    output_path = output_dir / output_name
                    stats = self.process_file(tmx_path, output_path, fmt, convert_options)
                    results[str(tmx_path)] = stats
        
        return results
    
    def merge_files(
        self,
        tmx_files: List[Path],
        output_path: Path,
        fmt: OutputFormat = OutputFormat.JSONL,
        convert_options: Optional[ConvertOptions] = None,
    ) -> Dict[str, int]:
        """Merge multiple TMX files into one output."""
        all_units = []
        
        for tmx_path in tmx_files:
            parser = TMXParser(tmx_path)
            units = parser.parse_all()
            all_units.extend(units)
        
        stats = {
            "input_units": len(all_units),
            "after_clean": len(all_units),
            "after_dedupe": len(all_units),
            "output_units": len(all_units),
        }
        
        if self.clean:
            cleaner = DataCleaner(self.clean_config)
            all_units = cleaner.clean_units(all_units)
            stats["after_clean"] = len(all_units)
        
        if self.dedupe:
            all_units = self.deduper.dedupe(list(all_units))
            stats["after_dedupe"] = len(all_units)
        
        opts = convert_options or ConvertOptions()
        converter = DataConverter(options=opts)
        converter.convert(all_units, output_path, fmt, instruction_tmpl=opts.instruction_template)
        stats["output_units"] = len(all_units)
        
        return stats


def find_tmx_files(pattern: str, base_dir: Optional[Path] = None) -> List[Path]:
    """Find TMX files matching a glob pattern."""
    base = base_dir or Path(".")
    if "*" in pattern or "?" in pattern:
        return list(base.glob(pattern))
    else:
        tmx_path = base / pattern
        return [tmx_path] if tmx_path.exists() else []
