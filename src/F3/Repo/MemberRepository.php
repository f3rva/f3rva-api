<?php
namespace F3\Repo;

/**
 * Member repository encapsulating all database access for a member.
 * 
 * @author bbischoff
 */
class MemberRepository {
	protected $db;

	public function __construct(Database $database) {
		$this->db = $database->getDatabase();
	}

	public function findAll() {
		$stmt = $this->db->query('
			select m.MEMBER_ID, m.F3_NAME from MEMBER m
			order by m.F3_NAME asc
		');
		
		return $stmt->fetchAll();
	}
	
	public function find($memberId) {
		$stmt = $this->db->prepare('
			select m.MEMBER_ID, m.F3_NAME from MEMBER m
			where m.MEMBER_ID=?
		');
		$stmt->execute([$memberId]);
		
		return $stmt->fetch();
	}
	
	/**
	 * Finds a member by the f3name in the member table or the alias table if available
	 */
	public function findByF3NameOrAlias($f3name) {
		$stmt = $this->db->prepare('
			select m.MEMBER_ID, m.F3_NAME from MEMBER m
				left outer join MEMBER_ALIAS ma ON m.MEMBER_ID=ma.MEMBER_ID
				where UPPER(m.F3_NAME)=? or UPPER(ma.F3_ALIAS)=?
		');
		$upperName = strtoupper($f3name);
		$stmt->execute([$upperName, $upperName]);
		
		return $stmt->fetch();
	}
	
	public function findExistingAlias($memberId, $associatedMemberId) {
		$stmt = $this->db->prepare('
			select ma.MEMBER_ID, ma.F3_ALIAS from MEMBER_ALIAS ma
				where ma.MEMBER_ID=?
			    and ma.F3_ALIAS=(select F3_NAME from MEMBER where MEMBER_ID=?)
		');
		$stmt->execute([$memberId, $associatedMemberId]);
		
		return $stmt->fetch();
	}
	
	public function findDuplicateWorkoutMembers($memberId, $associatedMemberId) {
		$stmt = $this->db->prepare('
			select wp.WORKOUT_ID, wp.NUM from 
				(select WORKOUT_ID, count(MEMBER_ID) as NUM from WORKOUT_PAX 
					where MEMBER_ID in (?, ?)
				group by WORKOUT_ID) wp
			where wp.NUM > 1;
		');
		$stmt->execute([$memberId, $associatedMemberId]);
		
		return $stmt->fetchAll();
	}
	
	public function findAliases($memberId) {
		$stmt = $this->db->prepare('
			select ma.MEMBER_ID, ma.F3_ALIAS from MEMBER_ALIAS ma
				where ma.MEMBER_ID=?
		');
		$stmt->execute([$memberId]);
		
		return $stmt->fetchAll();
	}
	
	public function findAttendanceCounts($startDate, $endDate, $order) {
		$sql = '
			select MEMBER_ID, F3_NAME, sum(WORKOUT_COUNT) as WORKOUT_COUNT, sum(Q_COUNT) as Q_COUNT, sum(Q_COUNT) / sum(WORKOUT_COUNT) as Q_RATIO
			from (
					select m.MEMBER_ID, m.F3_NAME, count(wp.WORKOUT_ID) as WORKOUT_COUNT, 0 as Q_COUNT from WORKOUT_PAX wp
					join MEMBER m on wp.MEMBER_ID = m.MEMBER_ID
					join WORKOUT w on wp.WORKOUT_ID = w.WORKOUT_ID
		';
		
		$hasDates = !empty($startDate) && !empty($endDate);
		if ($hasDates) {
			$sql = $sql . '
					where w.WORKOUT_DATE between ? and ?
			';
		}
		
		$sql = $sql . '
					group by m.F3_NAME
					
					union
					
					select m.MEMBER_ID, m.F3_NAME, 0, count(wq.WORKOUT_ID) from WORKOUT_Q wq
					join MEMBER m on wq.MEMBER_ID = m.MEMBER_ID
					join WORKOUT w on wq.WORKOUT_ID = w.WORKOUT_ID
		';

		if ($hasDates) {
			$sql = $sql . '
					where w.WORKOUT_DATE between ? and ?
			';
		}
		
		$sql = $sql . '
					group by m.F3_NAME
			) COUNTS
			group by MEMBER_ID, F3_NAME
		';
		
			
			
		switch ($order) {
			case 'workout':
				$sql = $sql . 'order by WORKOUT_COUNT desc';
				break;
			case 'q':
				$sql = $sql . 'order by Q_COUNT desc';
				break;
			case 'ratio':
				$sql = $sql . 'order by Q_RATIO desc';
				break;
			default:
				$sql = $sql . 'order by WORKOUT_COUNT desc';
				break;
		}
		$sql = $sql . ', 
			F3_NAME desc
		';
		
		$stmt = $this->db->prepare($sql);
		
		if ($hasDates) {
			$stmt->execute([$startDate, $endDate, $startDate, $endDate]);
		}
		else {
			$stmt->execute();
		}
		
		return $stmt->fetchAll();
	}
	
	public function findMemberStats($memberId) {
		$sql = '
			select w.NUM_WORKOUTS, q.NUM_QS, q.NUM_QS / w.NUM_WORKOUTS as Q_RATIO from (
				select count(*) as NUM_WORKOUTS from WORKOUT_PAX where MEMBER_ID=?
				) as w
				cross join (
				select count(*) as NUM_QS from WORKOUT_Q where MEMBER_ID=?
				) as q
		';
		$stmt = $this->db->prepare($sql);
		$stmt->execute([$memberId, $memberId]);
		
		return $stmt->fetch();
	}
	
	/**
	 * Inserts the user into the database and returns the id of the inserted member
	 */
	public function save($name) {
		$stmt = $this->db->prepare('
			insert into MEMBER(F3_NAME) values (?)
		');
		$stmt->execute([$name]);
		
		return $this->db->lastInsertId();		
	}
	
	/**
	 * Deletes a member
	 */
	public function delete($memberId) {
		$stmt = $this->db->prepare('
			delete from MEMBER
				where MEMBER_ID=?
		');
		
		$stmt->execute([$memberId]);
	}
	
	public function createAlias($memberId, $associatedMemberId) {
		$stmt = $this->db->prepare('
			insert into MEMBER_ALIAS(MEMBER_ID, F3_ALIAS)
				select m1.MEMBER_ID, m2.F3_NAME from MEMBER m1, MEMBER m2
			    where m1.MEMBER_ID = ? and m2.MEMBER_ID = ?
		');
		
		$stmt->execute([$memberId, $associatedMemberId]);
	}
	
	public function relinkWorkoutPax($memberId, $associatedMemberId) {
		$stmt = $this->db->prepare('
			update WORKOUT_PAX
				set MEMBER_ID=?
				where MEMBER_ID=?
		');
		
		$stmt->execute([$memberId, $associatedMemberId]);
	}
	
	public function relinkWorkoutQ($memberId, $associatedMemberId) {
		$stmt = $this->db->prepare('
			update WORKOUT_Q
				set MEMBER_ID=?
				where MEMBER_ID=?
		');
		
		$stmt->execute([$memberId, $associatedMemberId]);
	}
	
	public function relinkMemberAlias($memberId, $associatedMemberId) {
		$stmt = $this->db->prepare('
			update MEMBER_ALIAS
				set MEMBER_ID=?
				where MEMBER_ID=?
		');
		
		$stmt->execute([$memberId, $associatedMemberId]);
	}
	
	public function removeMemberFromWorkout($workoutId, $associatedMemberId) {
		$stmt = $this->db->prepare('
			delete from WORKOUT_PAX
				where WORKOUT_ID=? and MEMBER_ID=?
		');
		
		$stmt->execute([$workoutId, $associatedMemberId]);
	}
}


?>