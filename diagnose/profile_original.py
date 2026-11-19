"""Offline profile of an original AHA session; never executes recorded commands.

Timing categories are process lifetimes, not CPU/GPU utilization. Token totals
come from per-response usage records, not summed cumulative token_count events.
Only metadata is exported: no messages, reasoning, command bodies or credentials.
"""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def union_seconds(intervals):
    end = None
    total = 0.
    for lo, hi in sorted(intervals):
        if hi < lo:
            raise ValueError('Negative interval')
        total += max(0., hi - max(lo, end if end is not None else lo))
        end = max(hi, end if end is not None else hi)
    return total


def classify(command):
    # Test execution syntax, not mere mentions in log-reading commands.
    if re.search(r'acceptance review-images (?:runs/|/)', command):
        return 'external_review'
    if re.search(r'codex exec .*--image ', command, re.S):
        return 'review_transport_probe'
    if re.search(r'--python scenes/[^\s]+/validate_saved_scene', command):
        return 'saved_scene_validation'
    if re.search(r'--python scenes/[^\s]+/render_delivery', command):
        return 'preview_render'
    if re.search(r'python scenes/[^\s]+/prepare_layout', command):
        return 'layout_evidence'
    if re.search(r'python -m tools.layout_inspection.build_reference --video', command):
        return 'reference_preparation'
    if re.search(r'python scenes/[^\s]+/segment_furniture.py', command):
        return 'object_segmentation'
    if re.search(r'--python scenes/[^\s]+/(build_scene|revise_scene|finalize_scene|repair_|materials_|finish_)', command):
        return 'authored_build_and_stills'
    if re.search(r'python scenes/[^\s]+/(capture_original|inspect_capture).py', command):
        return 'source_capture'
    return 'other_tools_and_bookkeeping'


def profile(session, start, end):
    lower, upper = stamp(start), stamp(end)
    commands, compactions, usages = [], [], []
    item_counts = Counter()
    seen_items, seen_responses = set(), set()
    seen_calls = set()
    for line_number, line in enumerate(session.open(), 1):
        event = json.loads(line)
        ts = stamp(event['timestamp'])
        if ts < lower or ts > upper:
            continue
        payload = event.get('payload', {})
        if payload.get('type') in ('custom_tool_call', 'function_call'):
            seen_calls.add(payload['call_id'])
        if event['type'] == 'token_usage_record':
            rid = payload['response_id']
            if rid not in seen_responses:
                seen_responses.add(rid)
                usages.append({'response_id': rid, 'timestamp': event['timestamp'],
                               'usage': payload['usage'], 'source_line': line_number})
        if payload.get('type') != 'item_completed':
            continue
        item = payload.get('item', {})
        identity = item.get('id')
        if identity in seen_items:
            continue
        seen_items.add(identity)
        kind = item['type']
        item_counts[kind] += 1
        if kind not in ('CommandExecution', 'ContextCompaction'):
            continue
        lo = max(lower, payload['started_at_ms'] / 1000)
        hi = min(upper, payload['completed_at_ms'] / 1000)
        if lo > hi:
            continue
        row = {'id': identity, 'start_offset_s': lo-lower, 'end_offset_s': hi-lower,
               'wall_seconds': hi-lo, 'source_line': line_number}
        if kind == 'ContextCompaction':
            compactions.append(row)
            continue
        command = item.get('command', [])
        command = command[-1] if isinstance(command, list) else command
        row.update(process_id=item.get('process_id'), category=classify(command),
                   exit_code=item.get('exit_code'),
                   scripts=sorted(set(re.findall(r'scenes/ai2thor_floorplan209/([\w.-]+\.py)', command))),
                   log_files=sorted(set(re.findall(r'capture/([\w.-]+\.log)', command))))
        duration = item.get('duration') or {}
        row['reported_duration_s'] = duration.get('secs', 0) + duration.get('nanos', 0)/1e9
        commands.append(row)
    intervals = lambda rows: [(r['start_offset_s'],r['end_offset_s']) for r in rows]
    command_union = union_seconds(intervals(commands))
    compaction_union = union_seconds(intervals(compactions))
    all_union = union_seconds(intervals(commands+compactions))
    overlap = command_union + compaction_union - all_union
    buckets = defaultdict(list)
    for row in commands:
        buckets[row['category']].append(row)
    totals = Counter()
    compaction_usage = Counter()
    for row in usages:
        totals.update(row['usage'])
        offset = stamp(row['timestamp'])-lower
        if any(c['start_offset_s'] <= offset <= c['end_offset_s']+.1 for c in compactions):
            # Attribution by timestamp only; response ID retained for audit.
            compaction_usage.update(row['usage'])
    totals['uncached_input_tokens'] = totals['input_tokens']-totals['cached_input_tokens']
    return {'session': str(session.resolve()), 'session_sha256': hashlib.sha256(session.read_bytes()).hexdigest(),
            'start_utc': start, 'end_utc': end, 'observed_wall_seconds': upper-lower,
            'item_counts': dict(item_counts), 'tool_call_count': len(seen_calls),
            'response_usage_count': len(usages), 'usage_including_compaction': dict(totals),
            'usage_timestamped_during_compaction': dict(compaction_usage),
            'wall_partition_seconds': {'command_only': command_union-overlap,
                'compaction_only': compaction_union-overlap, 'command_and_compaction': overlap,
                'outside_recorded_commands_and_compaction': upper-lower-all_union},
            'categories': {k:{'count':len(v), 'duration_sum_s':sum(r['wall_seconds'] for r in v),
                             'interval_union_s':union_seconds(intervals(v)),
                             'nonzero_exit_count':sum(r['exit_code'] not in (0,None) for r in v)}
                           for k,v in buckets.items()},
            'commands': commands, 'compactions':compactions, 'responses':usages,
            'limitations': [
                'Command lifetime includes subprocesses, I/O, waits and shutdown; not GPU or CPU active time.',
                'Category intervals overlap. Only wall_partition_seconds is additive across categories.',
                'Outside recorded commands/compaction includes model turns, tool dispatch, image inspection and unknown overhead; not pure inference time.',
                'Classification is heuristic and auditable by source_line; mixed commands cannot be subdivided.',
                'Nested reviewer usage is separate; this is not invoice cost.',
                'No causal speedup or full dependency critical path can be derived from these intervals alone.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if stamp(args.end) <= stamp(args.start):
        parser.error('End must follow start')
    if args.output.exists():
        parser.error('Output directory must be new')
    result = profile(args.session, args.start, args.end)
    args.output.mkdir(parents=True)
    (args.output/'profile.json').write_text(json.dumps(result, indent=2)+'\n')
    with (args.output/'commands.csv').open('w', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(result['commands'][0]))
        writer.writeheader();writer.writerows(result['commands'])
    print(json.dumps({k:v for k,v in result.items() if k not in ('commands','responses')}, indent=2))


if __name__ == '__main__':
    main()
