#!/usr/bin/env python3
"""
Проверка статуса analyzed_by для всех обработанных групп комментариев
"""
import sqlite3

# Все 30 обработанных post_id
PROCESSED_POST_IDS = [
    # Партия 1
    758, 747, 733, 732, 731, 730, 729, 728, 726, 720,
    # Партия 2
    719, 718, 717, 690, 689, 688, 687, 686, 685, 684,
    # Партия 3
    681, 680, 679, 293, 292, 291, 290, 156, 155, 154
]

def check_status():
    conn = sqlite3.connect('data/experts.db')
    c = conn.cursor()

    placeholders = ','.join(['?'] * len(PROCESSED_POST_IDS))
    c.execute(f'''
        SELECT post_id, expert_id, analyzed_by, has_drift
        FROM comment_group_drift
        WHERE post_id IN ({placeholders})
        ORDER BY post_id DESC
    ''', PROCESSED_POST_IDS)

    results = c.fetchall()

    print(f'\n{"="*70}')
    print(f'Проверка статуса {len(results)} обработанных групп комментариев')
    print(f'{"="*70}\n')
    print(f'{"Post ID":<10} {"Эксперт":<15} {"Статус":<20} {"Дрифт"}')
    print('-' * 70)

    pending_count = 0
    drift_on_synced_count = 0
    other_count = 0
    pending_posts = []

    for post_id, expert_id, analyzed_by, has_drift in results:
        drift_str = '✓ Да' if has_drift else '✗ Нет'
        status_display = analyzed_by if analyzed_by else 'NULL'
        print(f'{post_id:<10} {expert_id:<15} {status_display:<20} {drift_str}')

        if analyzed_by == 'pending':
            pending_count += 1
            pending_posts.append((post_id, expert_id))
        elif analyzed_by == 'drift-on-synced':
            drift_on_synced_count += 1
        else:
            other_count += 1

    print('\n' + '=' * 70)
    print(f'ИТОГОВАЯ СТАТИСТИКА:')
    print('-' * 70)
    print(f'  ✓ drift-on-synced: {drift_on_synced_count} групп ({drift_on_synced_count/len(results)*100:.1f}%)')
    print(f'  ⚠️  pending: {pending_count} групп ({pending_count/len(results)*100:.1f}%)')
    if other_count > 0:
        print(f'  ? другой статус: {other_count} групп')

    if pending_count > 0:
        print(f'\n{"="*70}')
        print(f'⚠️  ПРОБЛЕМА: {pending_count} групп остались в статусе pending!')
        print(f'{"="*70}')
        print('\nГруппы со статусом pending:')
        for post_id, expert_id in pending_posts:
            print(f'  - Post ID {post_id} ({expert_id})')
        print('\nЭти группы нужно обработать повторно!')
    else:
        print(f'\n✅ Все {len(results)} групп успешно обработаны!')

    print('=' * 70 + '\n')

    conn.close()

if __name__ == '__main__':
    check_status()
