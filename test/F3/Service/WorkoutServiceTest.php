<?php
namespace F3\Service;

use F3\Dao\ScraperDao;
use F3\Model\AO;
use F3\Model\Member;
use F3\Model\Response;
use F3\Repo\Database;
use F3\Repo\WorkoutRepository;
use PHPUnit\Framework\TestCase;

/**
 * @covers \F3\Service\WorkoutService
 * @backupGlobals enabled
 */
class WorkoutServiceTest extends TestCase {

    /** @var \PHPUnit\Framework\MockObject\MockObject $workoutRepoMock */
    private $workoutRepoMock;
    /** @var \PHPUnit\Framework\MockObject\MockObject $memberServiceMock */
    private $memberServiceMock;
    /** @var \PHPUnit\Framework\MockObject\MockObject $scraperDaoMock */
    private $scraperDaoMock;
    /** @var \PHPUnit\Framework\MockObject\MockObject $databaseMock */
    private $databaseMock;
    /** @var \F3\Repo\WorkoutRepository $workoutRepo */
    private $workoutRepo;
    /** @var \F3\Service\MemberService $memberService */
    private $memberService;
    /** @var \F3\Dao\ScraperDao $scraperDao */
    private $scraperDao;
    /** @var \F3\Repo\Database $database */
    private $database;
    
    protected function setUp(): void
    {
        $this->workoutRepoMock = $this->getMockBuilder(WorkoutRepository::class)
                                ->disableOriginalConstructor()
                                ->getMock();
        $this->memberServiceMock = $this->getMockBuilder(MemberService::class)
                                ->disableOriginalConstructor()
                                ->getMock();
        $this->scraperDaoMock = $this->getMockBuilder(ScraperDao::class)
                                ->disableOriginalConstructor()
                                ->getMock();
        $this->databaseMock = $this->getMockBuilder(Database::class)
                             ->disableOriginalConstructor()
                             ->getMock();
        
        $this->workoutRepo = $this->workoutRepoMock;
        $this->memberService = $this->memberServiceMock;
        $this->scraperDao = $this->scraperDaoMock;
        $this->database = $this->databaseMock;
    }

    public function testGetWorkout() {   
        $workoutArray = $this->createTestWorkoutArray();

        // mock the second AO and Q
        $workout2 = array();
        $workout2['WORKOUT_ID'] = '1';
        $workout2['AO_ID'] = '6';
        $workout2['AO'] = 'Hoedown';
        $workout2['Q_ID'] = '7';
        $workout2['Q'] = 'Lockjaw';
        array_push($workoutArray, $workout2);

        $this->workoutRepoMock->method('find')
                              ->willReturn($workoutArray);

        $paxArray = $this->createTestPaxArray();
        $this->workoutRepoMock->method('findPax')
                              ->willReturn($paxArray);

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $result = $workoutService->getWorkout(1);

        $this->assertEquals('1', $result->getWorkoutId(), 'workout id mismatch');
        $this->assertEquals('https://f3rva.org/2021/12/30/test-post', $result->getBackblastURL(), 'url mismatch');
        $this->assertEquals('5', $result->getPaxCount(), 'pax count mismatch');
        $this->assertEquals('Test Post', $result->getTitle(), 'title mismatch');
        $this->assertEquals('2021-12-30', $result->getWorkoutDate(), 'date mismatch');
        $this->assertEquals('Spider Run', $result->getAo()['2'], 'ao mismatch');
        $this->assertEquals('Hoedown', $result->getAo()['6'], 'ao2 mismatch');
        $this->assertEquals('Splinter', $result->getQ()['3'], 'q mismatch');
        $this->assertEquals('Lockjaw', $result->getQ()['7'], 'q2 mismatch');
        $this->assertEquals('4', $result->getPax()['4']->getMemberId(), 'pax member id mismatch');
        $this->assertEquals('Upchuck', $result->getPax()['4']->getF3Name(), 'pax name mismatch');
    }

    public function testGetWorkouts() {
        $workoutArray = $this->createTestWorkoutArray();

        // mock the second AO and Q
        $workout2 = array();
        $workout2['WORKOUT_ID'] = '1';
        $workout2['AO_ID'] = '6';
        $workout2['AO'] = 'Hoedown';
        $workout2['Q_ID'] = '7';
        $workout2['Q'] = 'Lockjaw';
        array_push($workoutArray, $workout2);

        $this->workoutRepoMock->method('findAllByDateRange')
                        ->willReturn($workoutArray);
        $this->workoutRepoMock->method('findMostRecentWorkoutDate')
                        ->willReturn('2021-12-30');

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $result = $workoutService->getWorkouts();

        $this->assertEquals('1', $result['1']->getWorkoutId(), 'workout id mismatch');
        $this->assertEquals('https://f3rva.org/2021/12/30/test-post', $result['1']->getBackblastURL(), 'url mismatch');
        $this->assertEquals('5', $result['1']->getPaxCount(), 'pax count mismatch');
        $this->assertEquals('Test Post', $result['1']->getTitle(), 'title mismatch');
        $this->assertEquals('2021-12-30', $result['1']->getWorkoutDate(), 'date mismatch');
        $this->assertEquals('Spider Run', $result['1']->getAo()['2'], 'ao mismatch');
        $this->assertEquals('Hoedown', $result['1']->getAo()['6'], 'ao2 mismatch');
        $this->assertEquals('Splinter', $result['1']->getQ()['3'], 'q mismatch');
        $this->assertEquals('Lockjaw', $result['1']->getQ()['7'], 'q2 mismatch');
    }

    public function testGetWorkoutsByAo() {
        $workoutArray = $this->createTestWorkoutArray();

        $this->workoutRepoMock->method('findAllByAo')
                        ->willReturn($workoutArray);

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $result = $workoutService->getWorkoutsByAo('5');

        $this->assertEquals('1', $result['1']->getWorkoutId(), 'workout id mismatch');
        $this->assertEquals('https://f3rva.org/2021/12/30/test-post', $result['1']->getBackblastURL(), 'url mismatch');
    }

    public function testGetWorkoutsByQ() {
        $workoutArray = $this->createTestWorkoutArray();

        $this->workoutRepoMock->method('findAllByQ')
                        ->willReturn($workoutArray);

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $result = $workoutService->getWorkoutsByQ('5');

        $this->assertEquals('1', $result['1']->getWorkoutId(), 'workout id mismatch');
        $this->assertEquals('https://f3rva.org/2021/12/30/test-post', $result['1']->getBackblastURL(), 'url mismatch');
    }

    public function testGetWorkoutsByPax() {
        $workoutArray = $this->createTestWorkoutArray();

        $this->workoutRepoMock->method('findAllByPax')
                        ->willReturn($workoutArray);

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $result = $workoutService->getWorkoutsByPax('5');

        $this->assertEquals('1', $result['1']->getWorkoutId(), 'workout id mismatch');
        $this->assertEquals('https://f3rva.org/2021/12/30/test-post', $result['1']->getBackblastURL(), 'url mismatch');
    }

    public function testParsePost() {
        $this->scraperDaoMock->method('parsePost')
                             ->willReturn('some value');
        
        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $result = $workoutService->parsePost('https://testurl');
        $this->assertEquals('some value', $result, 'result mismatch');
    }

    public function testAddWorkout() {
        $additionalInfo = (object) array(
			'author' => 'Splinter',
			'date' => array('year' => 2022, 'month' => 1, 'day' => 5),
			'pax' => ['Kubota', 'Upchuck'],
			'q' => ['Splinter'], 
			'tags' => ['First Watch'], 
			'title' => 'Fun Title'
		);
        $this->scraperDaoMock->method('parsePost')
                             ->willReturn($additionalInfo);
        $pdoMock = $this->getMockBuilder(\PDO::class)
                        ->disableOriginalConstructor()
                        ->getMock();
    
        $this->databaseMock->method('getDatabase')
                           ->willReturn($pdoMock);
        $this->workoutRepoMock->method('save')
                              ->willReturn('123');

        // mock ao
        $ao = (object) array('aoId' => '5', 'description' => 'Spider Run');
        $this->workoutRepoMock->method('selectOrAddAo')
                              ->willReturn($ao);
        
        $member = new Member();
        $member->setMemberId('1');
        $this->memberServiceMock->method('getOrAddMember')
                                ->willReturn($member);

        $pdoMock->expects($this->once())
                ->method('commit');

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $response = $workoutService->addWorkout((object) array( 'post' => (object) array( 'url' => 'https://testurl')));

        $this->assertEquals(Response::SUCCESS, $response->getCode(), 'expected success');
        $this->assertEquals('123', $response->getId(), 'id mismatch');
    }

    public function testAddWorkoutFutureDate() {
        $additionalInfo = (object) array(
			'author' => 'Splinter',
			'date' => array('year' => 2122, 'month' => 1, 'day' => 5),
			'pax' => ['Kubota', 'Upchuck'],
			'q' => ['Splinter'], 
			'tags' => ['First Watch'], 
			'title' => 'Fun Title'
		);
        $this->scraperDaoMock->method('parsePost')
                             ->willReturn($additionalInfo);

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $response = $workoutService->addWorkout((object) array( 'post' => (object) array( 'url' => 'https://testurl')));

        $this->assertEquals(Response::NOT_APPLICABLE, $response->getCode(), 'expected not applicable');
        $this->assertNull($response->getId(), 'id expected to be null');
    }

    public function testAddWorkoutFailure() {
        $additionalInfo = (object) array(
			'author' => 'Splinter',
			'date' => array('year' => 2022, 'month' => 1, 'day' => 5),
			'pax' => ['Kubota', 'Upchuck'],
			'q' => ['Splinter'], 
			'tags' => ['First Watch'], 
			'title' => 'Fun Title'
		);
        $this->scraperDaoMock->method('parsePost')
                             ->willReturn($additionalInfo);
        $pdoMock = $this->getMockBuilder(\PDO::class)
                        ->disableOriginalConstructor()
                        ->getMock();
    
        $this->databaseMock->method('getDatabase')
                           ->willReturn($pdoMock);
        $this->workoutRepoMock->method('save')
                              ->willReturn('123');

        // mock ao
        $ao = (object) array('aoId' => '5', 'description' => 'Spider Run');
        $this->workoutRepoMock->method('selectOrAddAo')
                              ->willReturn($ao);
        
        $member = new Member();
        $member->setMemberId('1');
        $this->memberServiceMock->method('getOrAddMember')
                                ->willReturn($member);

        $pdoMock->method('beginTransaction')
                ->willThrowException(new \Exception());
        $pdoMock->expects($this->once())
                ->method('rollback');

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $response = $workoutService->addWorkout((object) array( 'post' => (object) array( 'url' => 'https://testurl')));

        $this->assertEquals(Response::FAILURE, $response->getCode(), 'expected failure');
        $this->assertNotNull($response->getMessage(), 'expected a detail message');
    }

    public function testRefreshWorkout() {
        // mock workouts
        $workoutArray = $this->createTestWorkoutArray();
        $this->workoutRepoMock->method('find')
                              ->willReturn($workoutArray);

        // mock pax
        $paxArray = $this->createTestPaxArray();
        $this->workoutRepoMock->method('findPax')
                              ->willReturn($paxArray);

        // mock parse post
        $additionalInfo = (object) array(
			'author' => 'Splinter',
			'date' => array('year' => 2022, 'month' => 1, 'day' => 5),
			'pax' => ['Kubota', 'Upchuck'],
			'q' => ['Splinter'], 
			'tags' => ['First Watch'], 
			'title' => 'Fun Title'
		);
        $this->scraperDaoMock->method('parsePost')
                             ->willReturn($additionalInfo);

        $pdoMock = $this->getMockBuilder(\PDO::class)
                        ->disableOriginalConstructor()
                        ->getMock();
    
        $this->databaseMock->method('getDatabase')
                           ->willReturn($pdoMock);

        // mock ao
        $ao = (object) array('aoId' => '5', 'description' => 'Spider Run');
        $this->workoutRepoMock->method('selectOrAddAo')
                              ->willReturn($ao);
        
        $member = new Member();
        $member->setMemberId('1');
        $this->memberServiceMock->method('getOrAddMember')
                                ->willReturn($member);

        $pdoMock->expects($this->once())
                ->method('commit');

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $response = $workoutService->refreshWorkout('123');

        $this->assertEquals(Response::SUCCESS, $response->getCode(), 'expected success');
        $this->assertEquals('123', $response->getId(), 'id mismatch');
    }

    public function testRefreshWorkoutNotFound() {
        $workoutArray = $this->createTestWorkoutArray();
        $this->workoutRepoMock->method('find')
                              ->willReturn(array());

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $response = $workoutService->refreshWorkout('94949494');

        $this->assertEquals(Response::NOT_FOUND, $response->getCode(), 'expected not found');
        $this->assertNull($response->getId(), 'id should be null');
    }

    public function testRefreshWorkoutFutureDateNotApplicable() {
        // mock workouts
        $workoutArray = $this->createTestWorkoutArray();
        $this->workoutRepoMock->method('find')
                              ->willReturn($workoutArray);

        // mock pax
        $paxArray = $this->createTestPaxArray();
        $this->workoutRepoMock->method('findPax')
                              ->willReturn($paxArray);

        // mock parse post
        $additionalInfo = (object) array(
			'author' => 'Splinter',
			'date' => array('year' => 2122, 'month' => 1, 'day' => 5),
			'pax' => ['Kubota', 'Upchuck'],
			'q' => ['Splinter'], 
			'tags' => ['First Watch'], 
			'title' => 'Fun Title'
		);
        $this->scraperDaoMock->method('parsePost')
                             ->willReturn($additionalInfo);

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $response = $workoutService->refreshWorkout('123');

        $this->assertEquals(Response::NOT_APPLICABLE, $response->getCode(), 'expected not applicable');
        $this->assertNull($response->getId(), 'id expected to be null');
    }

    public function testRefreshWorkoutError() {
        // mock workouts
        $workoutArray = $this->createTestWorkoutArray();
        $this->workoutRepoMock->method('find')
                              ->willReturn($workoutArray);

        // mock pax
        $paxArray = $this->createTestPaxArray();
        $this->workoutRepoMock->method('findPax')
                              ->willReturn($paxArray);

        // mock parse post
        $additionalInfo = (object) array(
			'author' => 'Splinter',
			'date' => array('year' => 2022, 'month' => 1, 'day' => 5),
			'pax' => ['Kubota', 'Upchuck'],
			'q' => ['Splinter'], 
			'tags' => ['First Watch'], 
			'title' => 'Fun Title'
		);
        $this->scraperDaoMock->method('parsePost')
                             ->willReturn($additionalInfo);

        $pdoMock = $this->getMockBuilder(\PDO::class)
                        ->disableOriginalConstructor()
                        ->getMock();
    
        $this->databaseMock->method('getDatabase')
                           ->willReturn($pdoMock);

        $pdoMock->method('beginTransaction')
                ->willThrowException(new \Exception());
        $pdoMock->expects($this->never())
                ->method('commit');
        $pdoMock->expects($this->once())
                ->method('rollback');

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $response = $workoutService->refreshWorkout('123');

        $this->assertEquals(Response::FAILURE, $response->getCode(), 'expected failure');
        $this->assertNull($response->getId(), 'id expected to be null');
    }

    public function testDeleteWorkout() {
        $pdoMock = $this->getMockBuilder(\PDO::class)
                        ->disableOriginalConstructor()
                        ->getMock();
    
        $this->databaseMock->method('getDatabase')
                           ->willReturn($pdoMock);

        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $result = $workoutService->deleteWorkout(1);

        $this->assertTrue($result, 'delete expected to be true');
    }

    public function testDeleteWorkoutFalure() {
        $pdoMock = $this->getMockBuilder(\PDO::class)
                        ->disableOriginalConstructor()
                        ->getMock();    

        $this->databaseMock->method('getDatabase')
                     ->willReturn($pdoMock);
        $pdoMock->method('beginTransaction')
                ->willThrowException(new \Exception());
        $pdoMock->expects($this->once())
                ->method('rollback');
          
        $workoutService = new WorkoutService($this->memberService, $this->scraperDao, $this->workoutRepo, $this->database);
        $result = $workoutService->deleteWorkout(1);

        $this->assertFalse($result, 'delete expected to be false');
    }

    private function createTestWorkoutArray() {
        // create mocked response
        $workout = array();
        $workout['WORKOUT_ID'] = '1';
        $workout['BACKBLAST_URL'] = 'https://f3rva.org/2021/12/30/test-post';
        $workout['PAX_COUNT'] = '5';
        $workout['TITLE'] = 'Test Post';
        $workout['WORKOUT_DATE'] = '2021-12-30';
        $workout['AO_ID'] = '2';
        $workout['AO'] = 'Spider Run';
        $workout['Q_ID'] = '3';
        $workout['Q'] = 'Splinter';
        $workoutArray = array();
        array_push($workoutArray, $workout);

        return $workoutArray;
    }

    private function createTestPaxArray() {
        $pax = array();
        $pax['MEMBER_ID'] = '4';
        $pax['F3_NAME'] = 'Upchuck';
        $paxArray = array();
        array_push($paxArray, $pax);

        return $paxArray;
    }
}
