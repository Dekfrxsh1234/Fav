def check_winner(board: str):
  """
  รับบอร์ด XO (เช่น 'XOXOX--O-') แล้วคืนผล:
  - 'X' หรือ 'O' → มีผู้ชนะ
  - 'draw' → เสมอ
  - None → ยังไม่จบเกม
  """

  win_conditions = [
      [0, 1, 2], [3, 4, 5], [6, 7, 8],  # แถว
      [0, 3, 6], [1, 4, 7], [2, 5, 8],  # คอลัมน์
      [0, 4, 8], [2, 4, 6]              # ทแยง
  ]

  for condition in win_conditions:
      a, b, c = condition
      if board[a] != '-' and board[a] == board[b] == board[c]:
          return board[a]  # 'X' หรือ 'O'

  if '-' not in board:
      return 'draw'

  return None
