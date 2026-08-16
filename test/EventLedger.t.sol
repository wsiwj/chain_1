// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {EventLedger} from "../src/EventLedger.sol";

contract EventLedgerTest is Test {
    EventLedger ledger;

    address owner = address(this);            // test contract deploys => is owner + first agent
    address secondAgent = makeAddr("secondAgent");
    address stranger = makeAddr("stranger");
    address visitor = makeAddr("visitor");

    bytes32 constant HASH = keccak256("fake image bytes");

    function setUp() public {
        ledger = new EventLedger();
    }

    // --- 1. happy path: write a page, read it back ---
    function test_LogEvent() public {
        uint256 id = ledger.logEvent(HASH, "person at door");

        assertEq(id, 0);
        assertEq(ledger.eventCount(), 1);

        EventLedger.EventRecord memory rec = ledger.getEvent(0);
        assertEq(rec.evidenceHash, HASH);
        assertEq(rec.reporter, owner);
        assertEq(rec.label, "person at door");
        assertEq(rec.timestamp, uint40(block.timestamp));
    }

    // --- 2. strangers cannot write ---
    function test_StrangerCannotLog() public {
        vm.prank(stranger);
        vm.expectRevert(EventLedger.NotAgent.selector);
        ledger.logEvent(HASH, "should fail");
    }

    function test_StrangerCannotSetAccess() public {
        vm.prank(stranger);
        vm.expectRevert(EventLedger.NotAgent.selector);
        ledger.setAccess(visitor, true);
    }

    function test_StrangerCannotManageAgents() public {
        vm.prank(stranger);
        vm.expectRevert(EventLedger.NotOwner.selector);
        ledger.setAgent(stranger, true);
    }

    // --- 3. agent lifecycle: enable, use, disable ---
    function test_AgentLifecycle() public {
        ledger.setAgent(secondAgent, true);

        vm.prank(secondAgent);
        ledger.logEvent(HASH, "logged by second agent");
        assertEq(ledger.eventCount(), 1);

        ledger.setAgent(secondAgent, false);

        vm.prank(secondAgent);
        vm.expectRevert(EventLedger.NotAgent.selector);
        ledger.logEvent(HASH, "should now fail");
    }

    // --- 4. decideAccess is atomic: switch flips AND page is written ---
    function test_DecideAccessAtomic() public {
        assertFalse(ledger.isAllowed(visitor));

        uint256 id = ledger.decideAccess(visitor, true, HASH, "voice matched owner");

        assertTrue(ledger.isAllowed(visitor));
        assertEq(ledger.eventCount(), 1);
        assertEq(ledger.getEvent(id).label, "voice matched owner");
    }

    function test_AccessCanBeRevoked() public {
        ledger.setAccess(visitor, true);
        assertTrue(ledger.isAllowed(visitor));

        ledger.setAccess(visitor, false);
        assertFalse(ledger.isAllowed(visitor));
    }

    // --- 5. announcements fire with the right contents ---
    function test_EmitsEventLogged() public {
        vm.expectEmit(true, true, true, true);
        emit EventLedger.EventLogged(0, HASH, owner, "person at door");
        ledger.logEvent(HASH, "person at door");
    }

    function test_EmitsAccessChanged() public {
        vm.expectEmit(true, true, true, true);
        emit EventLedger.AccessChanged(visitor, true, owner);
        ledger.setAccess(visitor, true);
    }

    // --- bonus: fuzz — ANY hash/label round-trips intact ---
    function testFuzz_LogEventRoundTrip(bytes32 h, string calldata label) public {
        uint256 id = ledger.logEvent(h, label);
        EventLedger.EventRecord memory rec = ledger.getEvent(id);
        assertEq(rec.evidenceHash, h);
        assertEq(rec.label, label);
    }
}
