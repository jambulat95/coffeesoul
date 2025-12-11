from sqlalchemy import BigInteger, String, ForeignKey, Boolean, DateTime, select, desc, func, Integer, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from datetime import datetime

engine = create_async_engine(url='sqlite+aiosqlite:///bot.db')
async_session = async_sessionmaker(engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass

# --- ТАБЛИЦЫ ---

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    shop_id: Mapped[str] = mapped_column(String(50))
    position: Mapped[str] = mapped_column(String(50))

class Checklist(Base):
    __tablename__ = 'checklists'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    shop_id: Mapped[str] = mapped_column(String(50), nullable=True)
    target_position: Mapped[str] = mapped_column(String(50), nullable=True)
    # Поле schedule_days УДАЛЕНО
    
    questions = relationship("Question", back_populates="checklist", cascade="all, delete")

class Question(Base):
    __tablename__ = 'questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey('checklists.id'))
    text: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(20))
    needs_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    checklist = relationship("Checklist", back_populates="questions")

class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    checklist_id: Mapped[int] = mapped_column(ForeignKey('checklists.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    score_percent: Mapped[int] = mapped_column(Integer, default=0)

class Answer(Base):
    __tablename__ = 'answers'
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey('reports.id'))
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id'))
    answer_text: Mapped[str] = mapped_column(String(255), nullable=True)
    photo_id: Mapped[str] = mapped_column(String(255), nullable=True)
    points: Mapped[int] = mapped_column(Integer, default=0)

async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- ЗАПРОСЫ ---

async def get_user(tg_id: int):
    async with async_session() as session:
        return await session.scalar(select(User).where(User.tg_id == tg_id))

async def add_user(tg_id, full_name, role, shop_id, position):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            session.add(User(tg_id=tg_id, full_name=full_name, role=role, shop_id=shop_id, position=position))
            await session.commit()

# ИЗМЕНЕНИЕ: Убрали schedule_days
async def create_checklist(title: str, shop_id: str, target_position: str = None):
    async with async_session() as session:
        checklist = Checklist(title=title, shop_id=shop_id, target_position=target_position)
        session.add(checklist)
        await session.commit()
        await session.refresh(checklist)
        return checklist.id

# ИЗМЕНЕНИЕ: Убрали schedule_days
async def update_checklist(checklist_id: int, title: str = None, target_position: str = None):
    async with async_session() as session:
        checklist = await session.get(Checklist, checklist_id)
        if checklist:
            if title: checklist.title = title
            checklist.target_position = target_position
            await session.commit()

# ИЗМЕНЕНИЕ: Убрали фильтрацию по дням недели. Теперь показываем всё, что подходит по должности.
async def get_checklists_for_user(user_tg_id: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_tg_id))
        if not user: return []
        
        query = select(Checklist).where(
            ((Checklist.shop_id == user.shop_id) | (Checklist.shop_id == None)) &
            ((Checklist.target_position == user.position) | (Checklist.target_position == None))
        )
        result = await session.execute(query)
        return result.scalars().all()

# --- Остальные функции без изменений ---
async def get_all_positions():
    async with async_session() as session:
        query = select(User.position).where(User.role == 'worker').distinct()
        result = await session.execute(query)
        return result.scalars().all()

async def get_checklists():
    async with async_session() as session:
        result = await session.execute(select(Checklist))
        return result.scalars().all()

async def add_question(checklist_id, text, type, needs_photo):
    async with async_session() as session:
        session.add(Question(checklist_id=checklist_id, text=text, type=type, needs_photo=needs_photo))
        await session.commit()
        
async def get_questions(checklist_id):
    async with async_session() as session:
        result = await session.execute(select(Question).where(Question.checklist_id == checklist_id))
        return result.scalars().all()

async def create_report(user_tg_id, checklist_id):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == user_tg_id))
        report = Report(user_id=user.id, checklist_id=checklist_id, score_percent=0)
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report.id

async def save_answer_with_points(report_id, question_id, answer_text, photo_id, points):
    async with async_session() as session:
        session.add(Answer(report_id=report_id, question_id=question_id, answer_text=answer_text, photo_id=photo_id, points=points))
        await session.commit()

async def finish_report_calculation(report_id):
    async with async_session() as session:
        sum_points = await session.scalar(select(func.sum(Answer.points)).where(Answer.report_id == report_id)) or 0
        report = await session.get(Report, report_id)
        questions = await session.scalars(select(Question).where(Question.checklist_id == report.checklist_id))
        max_points = 0
        for q in questions:
            if q.type == 'binary': max_points += 1
            elif q.type == 'scale': max_points += 10
        percent = 0
        if max_points > 0: percent = int((sum_points / max_points) * 100)
        report.score_percent = percent
        await session.commit()
        return percent

async def get_monthly_stats_by_shop():
    async with async_session() as session:
        today = datetime.now()
        start_month = today.replace(day=1, hour=0, minute=0, second=0)
        query = (select(User.shop_id, func.avg(Report.score_percent), func.count(Report.id)).join(User, Report.user_id == User.id).where(Report.created_at >= start_month).group_by(User.shop_id))
        result = await session.execute(query)
        return result.all()

async def get_all_workers():
    async with async_session() as session: return await session.scalars(select(User).where(User.role == 'worker'))
async def get_all_shops():
    async with async_session() as session: return await session.scalars(select(User.shop_id).where(User.shop_id.is_not(None)).distinct())
async def get_employees_by_shop(shop_id: str):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.shop_id == shop_id).order_by(User.full_name))
        return result.scalars().all()
async def get_today_completed_checklist_ids(tg_id: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user: return []
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return await session.scalars(select(Report.checklist_id).where(Report.user_id == user.id).where(Report.created_at >= today_start))

async def get_all_reports_data():
    async with async_session() as session:
        query = select(Report).order_by(desc(Report.created_at))
        result = await session.execute(query)
        reports = result.scalars().all()
        export_data = []
        for report in reports:
            user = await session.scalar(select(User).where(User.id == report.user_id))
            checklist = await session.scalar(select(Checklist).where(Checklist.id == report.checklist_id))
            answers_result = await session.execute(select(Answer, Question).join(Question, Answer.question_id == Question.id).where(Answer.report_id == report.id))
            answers = answers_result.all()
            formatted_answers = []
            for ans, quest in answers:
                val = ans.answer_text if ans.answer_text else "-"
                formatted_answers.append(f"{quest.text}: {val} ({ans.points}б)")
            export_data.append({"date": report.created_at.strftime("%Y-%m-%d %H:%M"), "shop": user.shop_id, "employee": user.full_name, "checklist": checklist.title, "answers": " || ".join(formatted_answers)})
        return export_data

async def get_checklists_today():
    async with async_session() as session:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        query = select(Checklist).join(Report, Checklist.id == Report.checklist_id).where(Report.created_at >= today_start).distinct()
        result = await session.execute(query)
        return result.scalars().all()
        
async def get_reports_by_checklist_id(checklist_id: int):
    async with async_session() as session:
        query = select(Report, User).join(User, Report.user_id == User.id).where(Report.checklist_id == checklist_id).order_by(desc(Report.created_at)).limit(10)
        result = await session.execute(query)
        return result.all()

async def get_report_details(report_id: int):
    async with async_session() as session:
        report = await session.get(Report, report_id)
        user = await session.get(User, report.user_id)
        checklist = await session.get(Checklist, report.checklist_id)
        answers_res = await session.execute(select(Answer, Question).join(Question, Answer.question_id == Question.id).where(Answer.report_id == report_id))
        answers = answers_res.all()
        return {"report": report, "user": user, "checklist": checklist, "answers": answers}
        
async def get_employees_with_reports():
    async with async_session() as session:
        query = select(User).join(Report, User.id == Report.user_id).distinct()
        result = await session.execute(query)
        return result.scalars().all()

async def get_reports_by_user_tg_id(tg_id: int):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user: return []
        query = (select(Report, Checklist).join(Checklist, Report.checklist_id == Checklist.id).where(Report.user_id == user.id).order_by(desc(Report.created_at)).limit(10))
        result = await session.execute(query)
        return result.all()
        
async def delete_user(user_id: int):
    async with async_session() as session:
        user = await session.get(User, user_id)
        if user:
            await session.delete(user)
            await session.commit()
            return True
        return False